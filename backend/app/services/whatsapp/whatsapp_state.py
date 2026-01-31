import json
import os
import uuid
from typing import Any, Dict, Optional

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
OCR_STATE_TTL_SECONDS = 2 * 60 * 60
UPLOAD_META_TTL_SECONDS = 2 * 60 * 60
DEDUPE_TTL_SECONDS = 2 * 60 * 60
STEP_TTL_SECONDS = int(os.environ.get("WHATSAPP_STEP_TTL_SECONDS", "7200"))

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
