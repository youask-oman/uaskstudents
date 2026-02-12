from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.api_billing import get_current_user
from app.database import get_session
from app.models import Notification, User
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.notification_service import notification_service


router = APIRouter()


class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    body: str
    payload_json: Optional[Dict[str, Any]]
    severity: str
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]
    action_type: Optional[str]
    action_payload: Optional[Dict[str, Any]]


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    next_cursor: Optional[int]


class GenericOkResponse(BaseModel):
    ok: bool


class ReadAllResponse(BaseModel):
    ok: bool
    updated: int


class ThankResponse(BaseModel):
    ok: bool
    message: str


def _row_to_item(row: Notification) -> NotificationItem:
    return NotificationItem(
        id=row.id,
        type=row.type,
        title=row.title,
        body=row.body,
        payload_json=row.payload_json,
        severity=row.severity,
        is_read=row.is_read,
        created_at=row.created_at,
        read_at=row.read_at,
        action_type=row.action_type,
        action_payload=row.action_payload,
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    cursor: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.notifications_enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Notifications are disabled"})

    rows = notification_service.list_notifications(session, user_id=user.id, cursor=cursor, limit=limit)
    next_cursor = rows[-1].id if rows else None
    return NotificationListResponse(items=[_row_to_item(r) for r in rows], next_cursor=next_cursor)


@router.post("/notifications/{notification_id}/read", response_model=GenericOkResponse)
async def mark_notification_read(
    notification_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.notifications_enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Notifications are disabled"})

    row = notification_service.mark_read(session, user_id=user.id, notification_id=notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    session.commit()
    return GenericOkResponse(ok=True)


@router.post("/notifications/read_all", response_model=ReadAllResponse)
async def mark_all_notifications_read(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.notifications_enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Notifications are disabled"})

    updated = notification_service.mark_all_read(session, user_id=user.id)
    session.commit()
    return ReadAllResponse(ok=True, updated=updated)


@router.post("/notifications/{notification_id}/thank", response_model=ThankResponse)
async def thank_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.notifications_enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Notifications are disabled"})

    now = datetime.utcnow()
    since = now - timedelta(minutes=1)
    action_count = session.exec(
        select(func.count(Notification.id))
        .where(Notification.user_id == user.id)
        .where(Notification.action_type == "THANK")
        .where(Notification.created_at >= since)
    ).one()
    if int(action_count or 0) >= cfg.thank_per_minute_limit:
        raise HTTPException(status_code=429, detail={"code": "rate_limit_exceeded", "message": "Too many thank actions"})

    row = notification_service.mark_read(session, user_id=user.id, notification_id=notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification_service.create_notification(
        session,
        user_id=user.id,
        type="THANK_ACK",
        title="Thanks received",
        body="Your feedback was recorded.",
        severity="success",
        action_type="THANK",
        dedupe_key=f"thank_ack:{user.id}:{notification_id}:{now.strftime('%Y%m%d%H%M')}",
    )
    session.commit()
    return ThankResponse(ok=True, message="Thanks sent")


@router.get("/notifications/stream")
async def notifications_stream(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.notifications_enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Notifications are disabled"})

    async def event_generator():
        last_id = 0
        while True:
            rows = session.exec(
                select(Notification)
                .where(Notification.user_id == user.id)
                .where(Notification.id > last_id)
                .order_by(Notification.id.asc())
                .limit(20)
            ).all()
            if rows:
                for row in rows:
                    last_id = max(last_id, int(row.id or 0))
                    payload = _row_to_item(row).model_dump(mode="json")
                    yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

