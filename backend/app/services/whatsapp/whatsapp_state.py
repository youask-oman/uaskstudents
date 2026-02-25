import json
import os
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
OCR_STATE_TTL_SECONDS = 2 * 60 * 60
UPLOAD_META_TTL_SECONDS = 2 * 60 * 60
DEDUPE_TTL_SECONDS = 2 * 60 * 60
STEP_TTL_SECONDS = int(os.environ.get("WHATSAPP_STEP_TTL_SECONDS", "7200"))
PAIR_CODE_TTL_SECONDS = int(os.environ.get("WHATSAPP_PAIR_CODE_TTL_SECONDS", "600"))
PAIR_CODE_LENGTH = int(os.environ.get("WHATSAPP_PAIR_CODE_LENGTH", "8"))
PAIR_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _set_json(key: str, value: Dict[str, Any], ttl: int) -> None:
    get_redis().setex(key, ttl, json.dumps(value))


def _get_json(key: str) -> Optional[Dict[str, Any]]:
    raw = get_redis().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def mark_dedupe(message_id: Optional[str]) -> bool:
    if not message_id:
        return True
    key = f"whatsapp:dedupe:{message_id}"
    # NX ensures we only process once
    try:
        return bool(get_redis().set(key, "1", nx=True, ex=DEDUPE_TTL_SECONDS))
    except Exception:
        return True


def set_ocr_state(phone: str, data: Dict[str, Any]) -> None:
    key = f"whatsapp:ocr_state:{phone}"
    _set_json(key, data, OCR_STATE_TTL_SECONDS)


def get_ocr_state(phone: str) -> Optional[Dict[str, Any]]:
    key = f"whatsapp:ocr_state:{phone}"
    return _get_json(key)


def clear_ocr_state(phone: str) -> None:
    key = f"whatsapp:ocr_state:{phone}"
    get_redis().delete(key)


def set_step_pack(phone: str, data: Dict[str, Any]) -> None:
    key = f"whatsapp:steppack:{phone}"
    _set_json(key, data, STEP_TTL_SECONDS)


def get_step_pack(phone: str) -> Optional[Dict[str, Any]]:
    key = f"whatsapp:steppack:{phone}"
    return _get_json(key)


def clear_step_pack(phone: str) -> None:
    key = f"whatsapp:steppack:{phone}"
    get_redis().delete(key)


def create_upload_id() -> str:
    return uuid.uuid4().hex


def set_upload_meta(upload_id: str, data: Dict[str, Any]) -> None:
    key = f"whatsapp:upload:{upload_id}"
    _set_json(key, data, UPLOAD_META_TTL_SECONDS)


def get_upload_meta(upload_id: str) -> Optional[Dict[str, Any]]:
    key = f"whatsapp:upload:{upload_id}"
    return _get_json(key)


def create_pairing_code(user_id: int) -> Dict[str, Any]:
    """
    Create (or rotate) a short-lived one-time pairing code for a user.
    """
    code = "".join(secrets.choice(PAIR_CODE_ALPHABET) for _ in range(PAIR_CODE_LENGTH))
    user_key = f"wa:pair_code:user:{user_id}"
    code_key = f"wa:pair_code:{code}"
    redis = get_redis()
    prev_code = redis.get(user_key)
    if prev_code:
        redis.delete(f"wa:pair_code:{prev_code}")
    redis.setex(user_key, PAIR_CODE_TTL_SECONDS, code)
    redis.setex(code_key, PAIR_CODE_TTL_SECONDS, str(user_id))
    return {"code": code, "expires_in_seconds": PAIR_CODE_TTL_SECONDS}


def get_pairing_code_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Return current active pairing code for user if present.
    """
    redis = get_redis()
    user_key = f"wa:pair_code:user:{user_id}"
    code = redis.get(user_key)
    if not code:
        return None
    ttl = redis.ttl(user_key)
    return {
        "code": str(code),
        "expires_in_seconds": int(ttl if isinstance(ttl, int) and ttl > 0 else PAIR_CODE_TTL_SECONDS),
    }


def clear_pairing_code_for_user(user_id: int) -> bool:
    redis = get_redis()
    user_key = f"wa:pair_code:user:{user_id}"
    code = redis.get(user_key)
    deleted = 0
    if code:
        deleted += int(redis.delete(f"wa:pair_code:{code}") or 0)
    deleted += int(redis.delete(user_key) or 0)
    return deleted > 0


def consume_pairing_code(code: str) -> Optional[int]:
    """
    Resolve and consume one-time pairing code.
    """
    normalized = str(code or "").strip().upper()
    if not normalized:
        return None
    redis = get_redis()
    code_key = f"wa:pair_code:{normalized}"
    raw_user_id = redis.get(code_key)
    if not raw_user_id:
        return None
    try:
        user_id = int(raw_user_id)
    except Exception:
        return None
    redis.delete(code_key)
    redis.delete(f"wa:pair_code:user:{user_id}")
    return user_id


def log_whatsapp_event(event: Dict[str, Any], max_len: int = 200) -> None:
    key = "whatsapp:events"
    try:
        payload = dict(event)
        payload.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        if "text" in payload and isinstance(payload["text"], str):
            if len(payload["text"]) > max_len:
                payload["full_text"] = payload["text"]
                payload["text"] = payload["text"][: max_len - 3] + "..."
        get_redis().lpush(key, json.dumps(payload))
        get_redis().ltrim(key, 0, 199)
        get_redis().publish("whatsapp:events:stream", json.dumps(payload))
    except Exception:
        pass


def get_whatsapp_events(limit: int = 50, phone: Optional[str] = None, direction: Optional[str] = None) -> list:
    key = "whatsapp:events"
    try:
        raw = get_redis().lrange(key, 0, max(0, limit - 1))
        items = []
        for entry in raw:
            try:
                items.append(json.loads(entry))
            except json.JSONDecodeError:
                continue
        if phone:
            items = [i for i in items if i.get("from") == phone or i.get("to") == phone]
        if direction:
            items = [i for i in items if i.get("direction") == direction]
        return items
    except Exception:
        return []
