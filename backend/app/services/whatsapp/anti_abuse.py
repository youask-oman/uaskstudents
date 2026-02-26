import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha1
from typing import Any, Dict, List, Optional, Tuple

from app.services.whatsapp.ingress_security import increment_metric
from app.services.whatsapp.whatsapp_state import get_redis

_TOKEN_BUCKET_WITH_RETRY_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local current_tokens = tonumber(redis.call('HGET', key, 'tokens'))
local last_ts = tonumber(redis.call('HGET', key, 'ts'))
if current_tokens == nil then current_tokens = burst end
if last_ts == nil then last_ts = now end

local elapsed = now - last_ts
if elapsed < 0 then elapsed = 0 end
current_tokens = math.min(burst, current_tokens + (elapsed * rate))

local allowed = 0
local retry_after = 0
if current_tokens >= 1 then
  allowed = 1
  current_tokens = current_tokens - 1
else
  if rate > 0 then
    retry_after = math.ceil((1 - current_tokens) / rate)
    if retry_after < 1 then retry_after = 1 end
  else
    retry_after = 60
  end
end

redis.call('HSET', key, 'tokens', current_tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)
return {allowed, current_tokens, retry_after}
"""

_ABUSE_SCORE_LUA = """
local score_key = KEYS[1]
local ts_key = KEYS[2]
local now = tonumber(ARGV[1])
local add_points = tonumber(ARGV[2])
local decay_per_minute = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local score = tonumber(redis.call('GET', score_key) or '0')
local last_ts = tonumber(redis.call('GET', ts_key) or tostring(now))

local elapsed_sec = now - last_ts
if elapsed_sec < 0 then elapsed_sec = 0 end
local decay = (elapsed_sec / 60.0) * decay_per_minute
score = score - decay
if score < 0 then score = 0 end
score = score + add_points

redis.call('SETEX', score_key, ttl, tostring(score))
redis.call('SETEX', ts_key, ttl, tostring(now))
return score
"""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _utc_day_key(now: Optional[datetime] = None) -> str:
    ts = now or datetime.now(timezone.utc)
    return ts.strftime("%Y%m%d")


def _seconds_until_utc_midnight(now: Optional[datetime] = None) -> int:
    ts = now or datetime.now(timezone.utc)
    next_day = (ts + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_day - ts).total_seconds()))


def _minute_slot(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.strftime("%Y%m%d%H%M")


@dataclass
class GateDecision:
    allowed: bool
    reply: str = ""
    reason: str = ""
    retry_after_seconds: int = 0
    slow_lane: bool = False
    require_confirmation: bool = False
    drop_reason: str = ""


def _audit(action: str, actor: str, payload: Dict[str, Any]) -> None:
    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor[:128],
        "payload": payload,
    }
    key = "wa:audit:actions"
    try:
        redis = get_redis()
        redis.lpush(key, json.dumps(rec))
        redis.ltrim(key, 0, 999)
    except Exception:
        pass


def list_audit(limit: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        rows = get_redis().lrange("wa:audit:actions", 0, max(0, limit - 1))
    except Exception:
        return out
    for row in rows:
        try:
            out.append(json.loads(row))
        except Exception:
            continue
    return out


def _bucket_allow(key: str, rate: float, burst: int) -> Tuple[bool, int]:
    if rate <= 0 or burst <= 0:
        return True, 0
    redis = get_redis()
    now = time.time()
    ttl = max(10, int((burst / max(rate, 0.001)) * 3))
    try:
        result = redis.eval(_TOKEN_BUCKET_WITH_RETRY_LUA, 1, key, now, rate, burst, ttl)
        if isinstance(result, (list, tuple)) and len(result) >= 3:
            allowed = bool(int(result[0]))
            retry = int(float(result[2] or 0))
            return allowed, max(0, retry)
        return bool(result), 0
    except Exception:
        return True, 0


def _inc_realtime(name: str, amount: int = 1) -> None:
    key = f"wa:rt:{name}:{_minute_slot()}"
    try:
        redis = get_redis()
        redis.incrby(key, int(amount))
        redis.expire(key, _env_int("WHATSAPP_REALTIME_TTL_SECONDS", 48 * 3600))
    except Exception:
        pass


def _inc_drop(reason: str) -> None:
    clean = re.sub(r"[^a-z0-9_]+", "_", (reason or "").lower()).strip("_") or "unknown"
    _inc_realtime("dropped", 1)
    _inc_realtime(f"dropped_{clean}", 1)
    increment_metric(f"drop_{clean}")


def get_realtime_snapshot(minutes: int = 5) -> Dict[str, Any]:
    minutes = max(1, min(60, int(minutes)))
    redis = get_redis()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    slots = [(now - timedelta(minutes=i)).strftime("%Y%m%d%H%M") for i in range(minutes)]

    def _sum(name: str) -> int:
        total = 0
        for slot in slots:
            try:
                total += int(redis.get(f"wa:rt:{name}:{slot}") or 0)
            except Exception:
                continue
        return total

    reasons = [
        "signature_fail",
        "rate_limit",
        "quota",
        "dedup",
        "caps",
        "lock",
        "busy",
        "circuit",
        "abuse",
        "confirm",
    ]
    dropped_by_reason = {r: _sum(f"dropped_{r}") for r in reasons}
    return {
        "window_minutes": minutes,
        "inbound": _sum("inbound"),
        "enqueued": _sum("enqueued"),
        "dropped": _sum("dropped"),
        "dropped_by_reason": dropped_by_reason,
    }


def _offender_incr(user_id: Optional[int], field: str, amount: int = 1) -> None:
    if not user_id:
        return
    try:
        key = f"wa:off:user:{user_id}"
        redis = get_redis()
        redis.hincrby(key, field, int(amount))
        redis.expire(key, _env_int("WHATSAPP_OFFENDER_TTL_SECONDS", 14 * 24 * 3600))
    except Exception:
        pass


def top_offenders(limit: int = 25) -> List[Dict[str, Any]]:
    redis = get_redis()
    out: List[Dict[str, Any]] = []
    try:
        keys = list(redis.scan_iter(match="wa:off:user:*", count=500))
    except Exception:
        return out
    for key in keys:
        try:
            user_id = int(str(key).split(":")[-1])
            row = redis.hgetall(key) or {}
            score = int(row.get("score", 0))
            out.append(
                {
                    "user_id": user_id,
                    "lock_count": int(row.get("lock_count", 0)),
                    "rate_limit_hits": int(row.get("rate_limit_hits", 0)),
                    "quota_exceeded": int(row.get("quota_exceeded", 0)),
                    "abuse_hits": int(row.get("abuse_hits", 0)),
                    "score": score,
                }
            )
        except Exception:
            continue
    out.sort(
        key=lambda x: (
            x.get("lock_count", 0),
            x.get("rate_limit_hits", 0),
            x.get("quota_exceeded", 0),
            x.get("abuse_hits", 0),
            x.get("score", 0),
        ),
        reverse=True,
    )
    return out[: max(1, min(200, limit))]


def check_lock(user_id: Optional[int], phone: Optional[str]) -> Optional[Dict[str, Any]]:
    redis = get_redis()
    if user_id:
        key = f"wa:lock:user:{user_id}"
        try:
            ttl = int(redis.ttl(key))
        except Exception:
            ttl = -2
        if ttl > 0:
            return {"scope": "user", "ttl_seconds": ttl, "reason": redis.get(key) or "cooldown"}
    if phone:
        key = f"wa:lock:phone:{phone}"
        try:
            ttl = int(redis.ttl(key))
        except Exception:
            ttl = -2
        if ttl > 0:
            return {"scope": "phone", "ttl_seconds": ttl, "reason": redis.get(key) or "cooldown"}
    return None


def list_locks(limit: int = 200) -> List[Dict[str, Any]]:
    redis = get_redis()
    rows: List[Dict[str, Any]] = []
    for pattern in ("wa:lock:user:*", "wa:lock:phone:*"):
        try:
            keys = redis.scan_iter(match=pattern, count=500)
        except Exception:
            keys = []
        for key in keys:
            if len(rows) >= limit:
                return rows
            try:
                ttl = int(redis.ttl(key))
                if ttl <= 0:
                    continue
                reason = redis.get(key) or ""
                parts = str(key).split(":")
                rows.append(
                    {
                        "key": str(key),
                        "scope": parts[2] if len(parts) >= 3 else "unknown",
                        "subject": parts[3] if len(parts) >= 4 else "",
                        "ttl_seconds": ttl,
                        "reason": reason,
                    }
                )
            except Exception:
                continue
    rows.sort(key=lambda x: x.get("ttl_seconds", 0), reverse=True)
    return rows


def clear_lock(*, user_id: Optional[int], phone: Optional[str], actor: str = "system") -> Dict[str, Any]:
    redis = get_redis()
    deleted = 0
    if user_id:
        deleted += int(redis.delete(f"wa:lock:user:{user_id}") or 0)
    if phone:
        deleted += int(redis.delete(f"wa:lock:phone:{phone}") or 0)
    _audit("clear_lock", actor, {"user_id": user_id, "phone": phone, "deleted": deleted})
    return {"deleted": deleted}


def force_lock(
    *,
    user_id: Optional[int],
    phone: Optional[str],
    seconds: int,
    reason: str,
    actor: str = "system",
) -> Dict[str, Any]:
    seconds = max(30, min(24 * 3600, int(seconds)))
    redis = get_redis()
    if user_id:
        redis.setex(f"wa:lock:user:{user_id}", seconds, reason)
        _offender_incr(user_id, "lock_count", 1)
    if phone:
        redis.setex(f"wa:lock:phone:{phone}", seconds, reason)
    _audit("force_lock", actor, {"user_id": user_id, "phone": phone, "seconds": seconds, "reason": reason})
    return {"ok": True, "seconds": seconds}


def get_unlock_request(user_id: int) -> Optional[Dict[str, Any]]:
    key = f"wa:unlock_request:user:{int(user_id)}"
    try:
        raw = get_redis().hgetall(key) or {}
    except Exception:
        return None
    if not raw:
        return None

    def _v(name: str) -> str:
        val = raw.get(name)
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="ignore")
        return str(val or "")

    return {
        "status": _v("status") or "pending",
        "requested_at": _v("requested_at"),
        "updated_at": _v("updated_at"),
        "phone": _v("phone"),
        "reason": _v("reason"),
    }


def submit_unlock_request(
    *,
    user_id: int,
    phone: Optional[str],
    reason: str = "",
    actor: str = "user",
) -> Dict[str, Any]:
    user_id = int(user_id)
    key = f"wa:unlock_request:user:{user_id}"
    now = datetime.now(timezone.utc).isoformat()
    existing = get_unlock_request(user_id)
    if existing and str(existing.get("status") or "").lower() == "pending":
        return {"status": "already_pending", "requested_at": existing.get("requested_at")}

    payload = {
        "status": "pending",
        "requested_at": now,
        "updated_at": now,
        "phone": str(phone or ""),
        "reason": str(reason or "")[:300],
    }
    redis = get_redis()
    redis.hset(key, mapping=payload)
    redis.expire(key, _env_int("WHATSAPP_UNLOCK_REQUEST_TTL_SECONDS", 7 * 24 * 3600))
    _audit(
        "unlock_request",
        actor,
        {"user_id": user_id, "phone": str(phone or ""), "reason": payload["reason"]},
    )
    return {"status": "pending", "requested_at": now}


def register_offense(user_id: Optional[int], phone: Optional[str], reason: str) -> Dict[str, Any]:
    redis = get_redis()
    now = int(time.time())
    cnt_key = f"wa:offense:count:user:{user_id}" if user_id else f"wa:offense:count:phone:{phone}"
    count = 0
    try:
        count = int(redis.incrby(cnt_key, 1))
        redis.expire(cnt_key, _env_int("WHATSAPP_OFFENSE_WINDOW_SECONDS", 3600))
    except Exception:
        pass

    t5 = _env_int("WHATSAPP_LOCK_5M_THRESHOLD", 3)
    t1h = _env_int("WHATSAPP_LOCK_1H_THRESHOLD", 6)
    tdisable = _env_int("WHATSAPP_DISABLE_THRESHOLD", 12)
    lock_seconds = 0
    if count >= t1h:
        lock_seconds = 3600
    elif count >= t5:
        lock_seconds = 300

    if lock_seconds > 0:
        force_lock(user_id=user_id, phone=phone, seconds=lock_seconds, reason=reason, actor="system:auto")

    if user_id:
        if reason == "rate_limit":
            _offender_incr(user_id, "rate_limit_hits")
        elif reason == "quota":
            _offender_incr(user_id, "quota_exceeded")
        elif reason == "abuse":
            _offender_incr(user_id, "abuse_hits")
        _offender_incr(user_id, "score", 1)

    return {"count": count, "lock_seconds": lock_seconds, "disable_recommended": bool(count >= tdisable), "at": now}


def _check_layer(name: str, key: str, rate_env: str, burst_env: str) -> Tuple[bool, int]:
    rate = _env_float(rate_env, 0.0)
    burst = _env_int(burst_env, 0)
    ok, retry_after = _bucket_allow(key, rate, burst)
    if not ok:
        increment_metric("rate_limited")
        _inc_drop("rate_limit")
        increment_metric(f"rate_limited_{name}")
    return ok, retry_after


def check_inbound_rate_limits(user_id: Optional[int], phone: str, ip: Optional[str]) -> Tuple[bool, int, str]:
    checks: List[Tuple[str, str, str, str]] = []
    if user_id:
        checks.append(("user_inbound", f"wa:rl:user:{user_id}", "WHATSAPP_RL_USER_RPS", "WHATSAPP_RL_USER_BURST"))
    checks.append(("phone_inbound", f"wa:rl:phone:{phone}", "WHATSAPP_RL_PHONE_RPS", "WHATSAPP_RL_PHONE_BURST"))
    checks.append(("global_inbound", "wa:rl:global:inbound", "WHATSAPP_RL_GLOBAL_INBOUND_RPS", "WHATSAPP_RL_GLOBAL_INBOUND_BURST"))
    if ip:
        checks.append(("ip_inbound", f"wa:rl:ip:{ip}", "WHATSAPP_RL_IP_RPS", "WHATSAPP_RL_IP_BURST"))

    for name, key, rate_env, burst_env in checks:
        ok, retry = _check_layer(name, key, rate_env, burst_env)
        if not ok:
            return False, retry, name
    return True, 0, ""


def check_solve_rate_limits(user_id: int, phone: str) -> Tuple[bool, int, str]:
    checks = [
        ("user_solve", f"wa:rl:solve:user:{user_id}", "WHATSAPP_RL_SOLVE_USER_RPS", "WHATSAPP_RL_SOLVE_USER_BURST"),
        ("global_solve", "wa:rl:global:solve", "WHATSAPP_RL_GLOBAL_SOLVE_RPS", "WHATSAPP_RL_GLOBAL_SOLVE_BURST"),
    ]
    for name, key, rate_env, burst_env in checks:
        ok, retry = _check_layer(name, key, rate_env, burst_env)
        if not ok:
            return False, retry, name
    return True, 0, ""


def check_ocr_rate_limits(user_id: int, phone: str) -> Tuple[bool, int, str]:
    checks = [
        ("user_ocr", f"wa:rl:ocr:user:{user_id}", "WHATSAPP_RL_OCR_USER_RPS", "WHATSAPP_RL_OCR_USER_BURST"),
        ("global_ocr", "wa:rl:global:ocr", "WHATSAPP_RL_GLOBAL_OCR_RPS", "WHATSAPP_RL_GLOBAL_OCR_BURST"),
    ]
    for name, key, rate_env, burst_env in checks:
        ok, retry = _check_layer(name, key, rate_env, burst_env)
        if not ok:
            return False, retry, name
    return True, 0, ""


def check_and_consume_quota(user_id: int, kind: str, amount: int = 1) -> Tuple[bool, int]:
    redis = get_redis()
    amount = max(1, int(amount))
    day = _utc_day_key()
    day_ttl = _seconds_until_utc_midnight()
    amount = int(amount)

    if kind == "solve":
        day_key = f"wa:quota:user:{user_id}:solves:day:{day}"
        burst_key = f"wa:quota:user:{user_id}:solves:10m"
        day_limit = _env_int("WHATSAPP_QUOTA_SOLVES_PER_DAY", 150)
        burst_limit = _env_int("WHATSAPP_QUOTA_SOLVES_PER_10M", 20)
        try:
            day_total = int(redis.incrby(day_key, amount))
            redis.expire(day_key, day_ttl)
            burst_total = int(redis.incrby(burst_key, amount))
            redis.expire(burst_key, 600)
        except Exception:
            return True, 0
        if day_total > day_limit:
            _inc_drop("quota")
            increment_metric("quota_reject")
            _offender_incr(user_id, "quota_exceeded")
            return False, day_ttl
        if burst_total > burst_limit:
            _inc_drop("quota")
            increment_metric("quota_reject")
            _offender_incr(user_id, "quota_exceeded")
            return False, int(get_redis().ttl(burst_key) or 60)
        return True, 0

    if kind == "ocr":
        day_key = f"wa:quota:user:{user_id}:ocr:day:{day}"
        day_limit = _env_int("WHATSAPP_QUOTA_OCR_PER_DAY", 50)
        try:
            total = int(redis.incrby(day_key, amount))
            redis.expire(day_key, day_ttl)
        except Exception:
            return True, 0
        if total > day_limit:
            _inc_drop("quota")
            increment_metric("quota_reject")
            _offender_incr(user_id, "quota_exceeded")
            return False, day_ttl
        return True, 0

    return True, 0


def _abuse_add_score(user_id: int, points: float) -> float:
    decay_per_minute = _env_float("WHATSAPP_ABUSE_DECAY_PER_MINUTE", 1.0)
    ttl = _env_int("WHATSAPP_ABUSE_SCORE_TTL_SECONDS", 7200)
    try:
        score = get_redis().eval(
            _ABUSE_SCORE_LUA,
            2,
            f"wa:abuse:user:{user_id}:score",
            f"wa:abuse:user:{user_id}:ts",
            float(time.time()),
            float(points),
            float(decay_per_minute),
            int(ttl),
        )
        return float(score or 0.0)
    except Exception:
        return 0.0


def _detect_abuse_points(user_id: int, text: str, has_media: bool) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    points = 0.0
    redis = get_redis()
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    max_chars = _env_int("WHATSAPP_MAX_TEXT_CHARS", 4000)

    if normalized:
        digest = sha1(normalized.encode("utf-8")).hexdigest()
        msg_key = f"wa:lastmsg:user:{user_id}"
        cnt_key = f"wa:lastmsg:user:{user_id}:cnt"
        try:
            prev = redis.get(msg_key)
            if prev == digest:
                same_count = int(redis.incrby(cnt_key, 1))
                redis.expire(cnt_key, 180)
                if same_count >= 3:
                    points += 4
                    reasons.append("repeated_identical_text")
            else:
                redis.setex(msg_key, 180, digest)
                redis.setex(cnt_key, 180, "1")
        except Exception:
            pass

    if normalized and len(normalized) >= int(max_chars * 0.9):
        points += 2
        reasons.append("near_cap_text")

    if normalized in {"hi", "hello", "test", "yo", "hey"}:
        spam_key = f"wa:spam:user:{user_id}:greet"
        try:
            spam_count = int(redis.incrby(spam_key, 1))
            redis.expire(spam_key, 120)
            if spam_count >= 4:
                points += 3
                reasons.append("greeting_spam")
        except Exception:
            pass

    if has_media:
        media_key = f"wa:media:user:{user_id}:burst"
        try:
            media_count = int(redis.incrby(media_key, 1))
            redis.expire(media_key, 300)
            if media_count >= _env_int("WHATSAPP_MAX_MEDIA_UPLOADS_5M", 8):
                points += 3
                reasons.append("media_burst")
        except Exception:
            pass

    return points, reasons


def evaluate_abuse(user_id: int, text: str, has_media: bool) -> Dict[str, Any]:
    points, reasons = _detect_abuse_points(user_id, text, has_media)
    score = _abuse_add_score(user_id, points)
    warn_t = _env_float("WHATSAPP_ABUSE_SCORE_THRESHOLD_WARN", 8.0)
    lock_t = _env_float("WHATSAPP_ABUSE_SCORE_THRESHOLD_LOCK", 15.0)
    require_yes = False
    redis = get_redis()

    confirm_key = f"wa:confirm:user:{user_id}"
    upper = (text or "").strip().upper()
    if redis.get(confirm_key) and upper == "YES":
        redis.delete(confirm_key)
        return {
            "score": score,
            "warn": False,
            "lock": False,
            "slow_lane": False,
            "require_confirmation": False,
            "confirmation_cleared": True,
            "reasons": reasons,
        }

    if score >= warn_t:
        require_yes = True
        redis.setex(confirm_key, _env_int("WHATSAPP_CONFIRM_TTL_SECONDS", 600), "1")

    lock = score >= lock_t
    slow_lane = score >= warn_t
    if lock:
        _offender_incr(user_id, "abuse_hits")
        _inc_drop("abuse")
        increment_metric("abuse_reject")
    return {
        "score": score,
        "warn": bool(score >= warn_t),
        "lock": bool(lock),
        "slow_lane": bool(slow_lane),
        "require_confirmation": bool(require_yes),
        "reasons": reasons,
    }


def circuit_flags() -> Dict[str, bool]:
    redis = get_redis()
    solve = str(redis.get("wa:circuit:disable_solve") or "0").lower() in {"1", "true", "yes", "on"}
    media = str(redis.get("wa:circuit:disable_media") or "0").lower() in {"1", "true", "yes", "on"}
    return {"disable_solve": solve, "disable_media": media}


def set_circuit_flags(disable_solve: Optional[bool], disable_media: Optional[bool], actor: str) -> Dict[str, bool]:
    redis = get_redis()
    if disable_solve is not None:
        redis.set("wa:circuit:disable_solve", "1" if disable_solve else "0")
    if disable_media is not None:
        redis.set("wa:circuit:disable_media", "1" if disable_media else "0")
    flags = circuit_flags()
    _audit("set_circuit_flags", actor, flags)
    return flags


def note_inbound() -> None:
    _inc_realtime("inbound", 1)


def note_enqueued() -> None:
    _inc_realtime("enqueued", 1)


def note_dedup_drop() -> None:
    _inc_drop("dedup")


def note_caps_drop() -> None:
    _inc_drop("caps")


def note_busy_drop() -> None:
    _inc_drop("busy")


def note_signature_drop() -> None:
    _inc_drop("signature_fail")


def note_lock_drop() -> None:
    _inc_drop("lock")


def note_circuit_drop() -> None:
    _inc_drop("circuit")


def note_confirm_drop() -> None:
    _inc_drop("confirm")


def code_attempt_key(phone: str) -> str:
    return f"wa:code_attempts:phone:{phone}:10m"


def register_invalid_code_attempt(phone: str) -> Dict[str, Any]:
    redis = get_redis()
    key = code_attempt_key(phone)
    max_attempts = _env_int("WHATSAPP_MAX_INVALID_CODE_ATTEMPTS_10M", 5)
    count = 0
    try:
        count = int(redis.incrby(key, 1))
        redis.expire(key, 600)
    except Exception:
        pass
    lock_applied = False
    if count >= max_attempts:
        force_lock(user_id=None, phone=phone, seconds=300, reason="invalid_code_bruteforce", actor="system:auto")
        lock_applied = True
        _inc_drop("abuse")
    return {"count": count, "lock_applied": lock_applied, "max": max_attempts}


def clear_code_attempts(phone: str) -> None:
    try:
        get_redis().delete(code_attempt_key(phone))
    except Exception:
        pass


def can_relink_user_today(user_id: int) -> bool:
    key = f"wa:link:churn:user:{user_id}:day:{_utc_day_key()}"
    limit = _env_int("WHATSAPP_MAX_PHONE_CHANGES_PER_DAY", 1)
    try:
        count = int(get_redis().get(key) or 0)
        return count < limit
    except Exception:
        return True


def mark_relink_change(user_id: int) -> None:
    key = f"wa:link:churn:user:{user_id}:day:{_utc_day_key()}"
    ttl = _seconds_until_utc_midnight()
    redis = get_redis()
    try:
        redis.incrby(key, 1)
        redis.expire(key, ttl)
    except Exception:
        pass


def ocr_queue_overloaded() -> bool:
    try:
        depth = int(get_redis().llen("whatsapp"))
    except Exception:
        return False
    threshold = _env_int("WHATSAPP_MAX_OCR_QUEUE_DEPTH", _env_int("WHATSAPP_MAX_QUEUE_DEPTH", 1000))
    return depth > threshold
