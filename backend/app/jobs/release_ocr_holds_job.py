from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.models import OCRJob
from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
from app.services.billing_exceptions import HoldAlreadyFinalizedError, HoldNotFoundError
from app.services.ocr.ocr_runtime_config_service import get_active_ocr_config


def run_release_ocr_holds_job(session: Session) -> int:
    runtime_cfg = get_active_ocr_config(session)
    ttl_minutes = max(int(runtime_cfg.ocr_hold_ttl_minutes or 10), 1)
    cutoff = datetime.utcnow() - timedelta(minutes=ttl_minutes)
    released = 0

    jobs = session.exec(
        select(OCRJob)
        .where(OCRJob.status == "completed")
        .where(OCRJob.accepted_solve_attempt_id.is_(None))
        .where(OCRJob.hold_request_id.is_not(None))
        .where(OCRJob.created_at <= cutoff)
    ).all()

    for job in jobs:
        try:
            billing_ledger_service_v2.release_hold(
                session=session,
                request_id=job.hold_request_id,
                attempt_id=job.id,
            )
            released += 1
        except (HoldAlreadyFinalizedError, HoldNotFoundError):
            continue

    session.commit()
    return released

