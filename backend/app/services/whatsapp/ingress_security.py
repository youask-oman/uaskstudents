import hmac
import json
import logging
import os
import re
import time
from hashlib import sha256
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request

from app.services.whatsapp.whatsapp_state import get_redis

logger = logging.getLogger(__name__)

SIG_TS_HEADER = "X-YouAsk-Timestamp"
SIG_NONCE_HEADER = "X-YouAsk-Nonce"
SIG_HEADER = "X-YouAsk-Signature"
REQUEST_ID_HEADER = "X-Request-Id"

_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local current_tokens = tonumber(redis.call('HGET', key, 'tokens'))
local last_ts = tonumber(redis.call('HGET', key, 'ts'))

if current_tokens == nil then
  current_tokens = burst
end
if last_ts == nil then
  last_ts = now
end

local elapsed = now - last_ts
if elapsed < 0 then elapsed = 0 end

current_tokens = math.min(burst, current_tokens + (elapsed * rate))
local allowed = 0
if current_tokens >= 1 then
  allowed = 1
  current_tokens = current_tokens - 1
end

redis.call('HSET', key, 'tokens', current_tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)

return {allowed, current_tokens}
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


def get_request_id(request: Request) -> str:
    incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if incoming:
        return incoming[:128]
    # Keep deterministic shape in logs/tasks without exposing sensitive data.
    return f"wa-{int(time.time() * 1000)}"


def _signing_secret() -> str:
    # Backward compatible fallback to existing internal key if dedicated secret is unset.
    return (os.getenv("WHATSAPP_SIGNING_SECRET") or os.getenv("WHATSAPP_INTERNAL_KEY") or "").strip()


async def verify_request_signature(request: Request) -> bytes:
    secret = _signing_secret()
    if not secret:
        logger.error("wa_signature_missing_server_secret")
        raise HTTPException(status_code=500, detail="WhatsApp signature secret is not configured")

    raw_body = await request.body()
    _verify_signature_headers(request, raw_body, secret)
    return raw_body


def verify_signature_headers_and_body(request: Request, raw_body: bytes) -> None:
    secret = _signing_secret()
    if not secret:
        logger.error("wa_signature_missing_server_secret")
        raise HTTPException(status_code=500, detail="WhatsApp signature secret is not configured")
    _verify_signature_headers(request, raw_body, secret)


def _verify_signature_headers(request: Request, raw_body: bytes, secret: str) -> None:
    ts_raw = (request.headers.get(SIG_TS_HEADER) or "").strip()
    nonce = (request.headers.get(SIG_NONCE_HEADER) or "").strip()
    signature = (request.headers.get(SIG_HEADER) or "").strip()
    if not ts_raw or not nonce or not signature:
        increment_metric("signature_fail")
        raise HTTPException(status_code=401, detail="Missing WhatsApp signature headers")

    try:
        ts = int(ts_raw)
    except Exception:
        increment_metric("signature_fail")
        raise HTTPException(status_code=401, detail="Invalid signature timestamp")

    now = int(time.time())
    allowed_drift = _env_int("WHATSAPP_SIGNATURE_MAX_DRIFT_SECONDS", 300)
    if abs(now - ts) > allowed_drift:
        increment_metric("signature_fail")
        logger.warning("wa_signature_timestamp_drift ts=%s now=%s drift=%s", ts, now, allowed_drift)
        raise HTTPException(status_code=401, detail="Stale WhatsApp request")

    expected_hex = hmac.new(
        secret.encode("utf-8"),
        f"{ts_raw}.{nonce}.".encode("utf-8") + raw_body,
        sha256,
    ).hexdigest()
    expected = f"sha256={expected_hex}"
    if not hmac.compare_digest(expected, signature):
        increment_metric("signature_fail")
        logger.warning("wa_signature_mismatch nonce=%s", nonce)
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")

    nonce_ttl = _env_int("WHATSAPP_SIGNATURE_NONCE_TTL_SECONDS", 600)
    nonce_key = f"wa:nonce:{nonce}"
    try:
        ok = bool(get_redis().set(nonce_key, "1", nx=True, ex=nonce_ttl))
    except Exception:
        ok = True
    if not ok:
        increment_metric("replay_reject")
        logger.warning("wa_replay_detected nonce=%s", nonce)
        raise HTTPException(status_code=409, detail="Replay detected")


def enforce_caps(payload: Dict[str, Any], raw_body: Optional[bytes] = None) -> None:
    text = str(payload.get("text") or "")
    has_image = bool(payload.get("hasImage"))
    upload_id = payload.get("upload_id")
    media_count = 1 if (has_image or upload_id) else 0

    max_text_chars = _env_int("WHATSAPP_MAX_TEXT_CHARS", 4000)
    max_media_count = _env_int("WHATSAPP_MAX_MEDIA_COUNT", 1)
    max_metadata_bytes = _env_int("WHATSAPP_MAX_METADATA_BYTES", 65536)

    if len(text) > max_text_chars:
        increment_metric("caps_reject")
        raise HTTPException(status_code=413, detail=f"Text too long. Max {max_text_chars} characters.")
    if media_count > max_media_count:
        increment_metric("caps_reject")
        raise HTTPException(status_code=413, detail=f"Too many media items. Max {max_media_count}.")
    if raw_body is not None and len(raw_body) > max_metadata_bytes:
        increment_metric("caps_reject")
        raise HTTPException(status_code=413, detail="Payload too large.")


def enforce_dedup(message_id: Optional[str]) -> bool:
    if not message_id:
        return True
    ttl = _env_int("WHATSAPP_DEDUP_TTL_SECONDS", 86400)
    key = f"wa:dedup:{message_id}"
    try:
        ok = bool(get_redis().set(key, "1", nx=True, ex=ttl))
    except Exception:
        ok = True
    if not ok:
        increment_metric("dedup_hit")
        return False
    return True


def _bucket_allow(key: str, rate: float, burst: int) -> bool:
    if rate <= 0 or burst <= 0:
        return True
    redis = get_redis()
    now = time.time()
    ttl = max(10, int((burst / max(rate, 0.001)) * 2))
    try:
        result = redis.eval(_TOKEN_BUCKET_LUA, 1, key, now, rate, burst, ttl)
        allowed = bool(int(result[0])) if isinstance(result, (list, tuple)) else bool(result)
        return allowed
    except Exception:
        # Fail-open to avoid taking production down if Redis script fails.
        return True


def enforce_rate_limit(user_id: int, normalized_phone: str) -> None:
    user_rate = _env_float("WHATSAPP_RL_USER_RPS", 0.5)
    user_burst = _env_int("WHATSAPP_RL_USER_BURST", 20)
    phone_rate = _env_float("WHATSAPP_RL_PHONE_RPS", 0.5)
    phone_burst = _env_int("WHATSAPP_RL_PHONE_BURST", 20)

    user_ok = _bucket_allow(f"wa:rl:user:{user_id}", user_rate, user_burst)
    phone_ok = _bucket_allow(f"wa:rl:phone:{normalized_phone}", phone_rate, phone_burst)
    if not user_ok or not phone_ok:
        increment_metric("rate_limited")
        raise HTTPException(status_code=429, detail="Too many WhatsApp requests. Please try again shortly.")


def queue_is_overloaded() -> bool:
    max_depth = _env_int("WHATSAPP_MAX_QUEUE_DEPTH", 1000)
    try:
        depth = int(get_redis().llen("whatsapp"))
        return depth > max_depth
    except Exception:
        return False


def increment_metric(name: str, amount: int = 1) -> None:
    key = f"wa:metrics:{name}"
    try:
        get_redis().incrby(key, int(amount))
        get_redis().expire(key, _env_int("WHATSAPP_METRICS_TTL_SECONDS", 7 * 24 * 3600))
    except Exception:
        pass


def get_metrics_snapshot() -> Dict[str, int]:
    keys = [
        "signature_fail",
        "replay_reject",
        "rate_limited",
        "quota_reject",
        "abuse_reject",
        "dedup_hit",
        "caps_reject",
        "busy_reject",
        "drop_signature_fail",
        "drop_rate_limit",
        "drop_quota",
        "drop_dedup",
        "drop_caps",
        "drop_lock",
        "drop_busy",
        "drop_circuit",
        "drop_abuse",
        "drop_confirm",
        "enqueue_success",
        "enqueue_failure",
        "worker_success",
        "worker_failure",
    ]
    out: Dict[str, int] = {}
    redis = get_redis()
    for k in keys:
        try:
            out[k] = int(redis.get(f"wa:metrics:{k}") or 0)
        except Exception:
            out[k] = 0
    return out


def parse_signed_json(raw_body: bytes) -> Dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    return payload


def normalize_phone(value: str) -> str:
    if not value:
        return ""
    # Keep only digits for consistent lookup and storage.
    digits = re.sub(r"\D+", "", value)
    return digits or value
