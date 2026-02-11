import logging
from celery import shared_task
from sqlmodel import Session

from app.database import engine
from app.jobs.release_ocr_holds_job import run_release_ocr_holds_job

logger = logging.getLogger(__name__)


@shared_task(name="ocr_hold_release_job")
def ocr_hold_release_task():
    """Periodic task to release stale OCR holds."""
    with Session(engine) as session:
        try:
            released = run_release_ocr_holds_job(session)
            return f"OCR hold release complete. Released: {released}"
        except Exception as e:
            logger.error(f"OCR hold release task failed: {e}")
            return f"Error: {e}"

