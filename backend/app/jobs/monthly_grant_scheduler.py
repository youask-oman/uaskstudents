"""
Monthly Grant Scheduler: Celery task for automatic credit grants.

This job runs on the 1st of each month and grants monthly credits
to all users enrolled in credit programs.

Phase 3 of Billing Redesign.
"""

import logging
from datetime import datetime
from sqlmodel import Session, select

from app.database import engine
from sqlmodel import Session, select
from app.models.credit_program_models import (
    CreditProgramDefinition,
    CreditProgramEnrollment,
)
from app.services.credit_program_service import credit_program_service
from app.services.billing_logger import log_billing_error
from app.services.billing_metrics import inc_billing_error

logger = logging.getLogger("billing.scheduler")


def get_current_grant_month() -> str:
    """Get current month in 'YYYY-MM' format."""
    return datetime.utcnow().strftime("%Y-%m")


def run_monthly_grant_job() -> dict:
    """
    Main entry point for the monthly grant job.
    
    This function:
    1. Finds all active enrollments
    2. Checks if they've already been granted for this month
    3. Issues grants for those that haven't
    
    Returns:
        Summary dict with counts
    """
    month = get_current_grant_month()
    logger.info(f"[MONTHLY_GRANT] Starting monthly grant job for {month}")
    
    stats = {
        "month": month,
        "enrollments_checked": 0,
        "grants_issued": 0,
        "grants_skipped": 0,
        "errors": 0,
    }
    
    with Session(engine) as session:
        # Get all active enrollments
        enrollments = session.exec(
            select(CreditProgramEnrollment)
            .where(CreditProgramEnrollment.status == "active")
        ).all()
        
        stats["enrollments_checked"] = len(enrollments)
        
        for enrollment in enrollments:
            try:
                # Skip if already granted this month
                if enrollment.last_grant_month == month:
                    stats["grants_skipped"] += 1
                    continue
                
                # Get program
                program = session.get(CreditProgramDefinition, enrollment.program_id)
                if not program or program.status != "active":
                    stats["grants_skipped"] += 1
                    continue
                
                # Skip if no monthly credits
                if program.monthly_gift_credits <= 0:
                    stats["grants_skipped"] += 1
                    continue
                
                # Issue grant
                lot = credit_program_service.grant_monthly_credits(
                    session=session,
                    user_id=enrollment.user_id,
                    program_id=enrollment.program_id,
                    month=month,
                )
                
                if lot:
                    stats["grants_issued"] += 1
                    logger.info(
                        f"[MONTHLY_GRANT] Granted {lot.credits_total} credits "
                        f"to user {enrollment.user_id} via program {enrollment.program_id}"
                    )
                else:
                    stats["grants_skipped"] += 1
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"[MONTHLY_GRANT] Error granting for enrollment {enrollment.id}: {e}"
                )
                log_billing_error(
                    user_id=enrollment.user_id,
                    error_code="MONTHLY_GRANT_FAILED",
                    error_message=str(e),
                    metadata={"enrollment_id": enrollment.id, "month": month},
                )
                inc_billing_error("MONTHLY_GRANT_FAILED")
        
        session.commit()
    
    logger.info(f"[MONTHLY_GRANT] Job complete: {stats}")
    return stats


# Celery task wrapper (if using Celery)
try:
    from celery import shared_task
    
    @shared_task(name="billing.monthly_grant")
    def monthly_grant_task():
        """Celery task for monthly grants."""
        return run_monthly_grant_job()
        
except ImportError:
    # Celery not installed - that's OK, function can be called directly
    pass


# Alternative: APScheduler job
def schedule_monthly_grant():
    """
    Schedule the monthly grant job to run on the 1st of each month.
    
    Usage with APScheduler:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_monthly_grant_job, 'cron', day=1, hour=0, minute=5)
        scheduler.start()
    """
    pass  # Implementation depends on scheduler choice
