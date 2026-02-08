import json
from typing import Any, Dict
from app.services.whatsapp.whatsapp_state import get_redis

def emit_attempt_event(attempt_id: str, request_id: str, phase: str, status: str = "active", metadata: Dict[str, Any] = None):
    """
    Emits a progress event for a solve attempt via Redis Pub/Sub.
    """
    payload = {
        "attempt_id": attempt_id,
        "request_id": request_id,
        "phase": phase,
        "status": status,
        "metadata": metadata or {}
    }
    channel = f"solve:attempt:{attempt_id}:events"
    get_redis().publish(channel, json.dumps(payload))
