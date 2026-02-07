
import logging
from celery import shared_task
from sqlmodel import Session, create_engine
import os
from app.database import engine
from app.jobs.grant_subscription_credits_job import run_grant_job
from app.jobs.expire_subscription_grants_job import run_expiry_job

logger = logging.getLogger(__name__)

@shared_task(name="subscription_grant_job")
def subscription_grant_task():
    """
    Periodic task to grant monthly credits.
    """
    with Session(engine) as session:
        try:
            count = run_grant_job(session)
            return f"Grant job complete. Granted: {count}"
        except Exception as e:
            logger.error(f"Subscription grant task failed: {e}")
            return f"Error: {e}"

@shared_task(name="subscription_expiry_job")
def subscription_expiry_task():
    """
    Periodic task to expire grants and close periods.
    """
    with Session(engine) as session:
        try:
            count = run_expiry_job(session)
            return f"Expiry job complete. Expired: {count}"
        except Exception as e:
            logger.error(f"Subscription expiry task failed: {e}")
            return f"Error: {e}"
