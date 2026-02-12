from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Notification


class NotificationService:
    def create_notification(
        self,
        session: Session,
        *,
        user_id: int,
        type: str,
        title: str,
        body: str,
        payload_json: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        action_type: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> Notification:
        if dedupe_key:
            existing = session.exec(
                select(Notification)
                .where(Notification.user_id == user_id)
                .where(Notification.dedupe_key == dedupe_key)
            ).first()
            if existing:
                return existing

        row = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            payload_json=payload_json,
            severity=severity,
            action_type=action_type,
            action_payload=action_payload,
            dedupe_key=dedupe_key,
        )
        session.add(row)
        try:
            session.flush()
            return row
        except IntegrityError:
            session.rollback()
            if dedupe_key:
                retry = session.exec(
                    select(Notification)
                    .where(Notification.user_id == user_id)
                    .where(Notification.dedupe_key == dedupe_key)
                ).first()
                if retry:
                    return retry
            raise

    def list_notifications(
        self,
        session: Session,
        *,
        user_id: int,
        cursor: Optional[int],
        limit: int,
    ) -> List[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if cursor:
            q = q.where(Notification.id < cursor)
        q = q.order_by(Notification.id.desc()).limit(limit)
        return session.exec(q).all()

    def mark_read(self, session: Session, *, user_id: int, notification_id: int) -> Optional[Notification]:
        row = session.get(Notification, notification_id)
        if not row or row.user_id != user_id:
            return None
        if not row.is_read:
            row.is_read = True
            row.read_at = datetime.utcnow()
            session.add(row)
            session.flush()
        return row

    def mark_all_read(self, session: Session, *, user_id: int) -> int:
        rows = session.exec(
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)  # noqa: E712
        ).all()
        now = datetime.utcnow()
        for row in rows:
            row.is_read = True
            row.read_at = now
            session.add(row)
        session.flush()
        return len(rows)


notification_service = NotificationService()

