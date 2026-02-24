from typing import Any, Dict
from app.services.attempt_event_service import append_attempt_event

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
    # Persist for replay, then fan out over pub/sub.
    append_attempt_event(
        attempt_id=attempt_id,
        request_id=request_id,
        event_type="phase",
        payload=payload,
    )
