from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import Session, func, select

from app.database import engine
from app.models import AttemptEvent
from app.services.whatsapp.whatsapp_state import get_redis


def _channel(attempt_id: str) -> str:
    return f"solve:attempt:{attempt_id}:events"


def append_attempt_event(
    *,
    attempt_id: str,
    event_type: str,
    payload: Dict[str, Any],
    request_id: Optional[str] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Persist event and fan it out over Redis pub/sub.
    Returns normalized payload including seq/type for SSE.
    """
    own_session = session is None
    db = session or Session(engine)
    try:
        max_seq = db.exec(select(func.max(AttemptEvent.seq)).where(AttemptEvent.attempt_id == attempt_id)).one()
        next_seq = int(max_seq or 0) + 1
        evt = AttemptEvent(
            attempt_id=attempt_id,
            seq=next_seq,
            type=event_type,
            payload=payload or {},
            created_at=datetime.utcnow(),
        )
        db.add(evt)
        db.commit()
        message = {
            "attempt_id": attempt_id,
            "request_id": request_id,
            "seq": next_seq,
            "type": event_type,
            "payload": payload or {},
            "ts": evt.created_at.isoformat(),
        }
        try:
            get_redis().publish(_channel(attempt_id), json.dumps(message))
        except Exception:
            pass
        return message
    finally:
        if own_session:
            db.close()


def fetch_attempt_events_after(
    *,
    attempt_id: str,
    after_seq: int,
    limit: int = 500,
    session: Optional[Session] = None,
) -> List[AttemptEvent]:
    own_session = session is None
    db = session or Session(engine)
    try:
        rows = db.exec(
            select(AttemptEvent)
            .where(AttemptEvent.attempt_id == attempt_id)
            .where(AttemptEvent.seq > int(after_seq))
            .order_by(AttemptEvent.seq.asc())
            .limit(max(1, int(limit)))
        ).all()
        return rows
    finally:
        if own_session:
            db.close()


def tail_attempt_pubsub(
    *,
    attempt_id: str,
    timeout: float = 1.0,
) -> Optional[Dict[str, Any]]:
    pubsub = get_redis().pubsub()
    try:
        pubsub.subscribe(_channel(attempt_id))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if not msg:
                continue
            raw = msg.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if not isinstance(raw, str):
                continue
            try:
                return json.loads(raw)
            except Exception:
                continue
        return None
    finally:
        try:
            pubsub.unsubscribe(_channel(attempt_id))
            pubsub.close()
        except Exception:
            pass

