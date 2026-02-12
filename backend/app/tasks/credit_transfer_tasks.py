from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session

from app.database import engine
from app.services.credit_transfer_service import credit_transfer_service
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.notification_service import notification_service
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="credit_transfer_expiry_job")
def credit_transfer_expiry_job() -> dict:
    now = datetime.utcnow()
    with Session(engine) as session:
        cfg = load_credit_transfer_config(session)
        if not cfg.enabled:
            return {"ok": True, "skipped": True, "reason": "feature_disabled"}

        refunded = credit_transfer_service.expire_and_refund_pending(session, now=now)
        if cfg.notifications_enabled:
            for transfer in refunded:
                if transfer.status == "REFUNDED":
                    notification_service.create_notification(
                        session,
                        user_id=transfer.sender_user_id,
                        type="CREDIT_TRANSFER_REFUNDED",
                        title="Pending transfer refunded",
                        body=f"Transfer to {transfer.recipient_email} expired and {float(transfer.amount):.2f} credits were refunded.",
                        severity="warning",
                        payload_json={"transfer_id": transfer.id},
                        dedupe_key=f"transfer_refunded:{transfer.id}",
                    )
        session.commit()
    logger.info("credit_transfer_expiry_job refunded=%s", len(refunded))
    return {"ok": True, "refunded": len(refunded)}

