"""
Nightly Reconciliation Job: Ensures ledger integrity.

This job runs nightly and:
1. Computes true balance from credit lots - consumed - holds
2. Compares with cached User.credits_balance
3. Logs discrepancies
4. Auto-corrects if RECONCILIATION_AUTOFIX_ENABLED flag is set
5. Creates ReconciliationRecord entries

Phase 5 of Billing Redesign.
"""

import logging
import os
from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass
from sqlmodel import Session, select

from app.database import engine, get_session_context
from sqlmodel import Session
from app.models import User, CreditLot, CreditHold
from app.models.credit_program_models import ReconciliationRecord
from app.services.billing_logger import log_billing_error
from app.services.billing_metrics import inc_billing_error

logger = logging.getLogger("billing.reconciliation")

# Feature flag
RECONCILIATION_AUTOFIX_ENABLED = os.environ.get(
    "RECONCILIATION_AUTOFIX_ENABLED", "false"
).lower() == "true"

# Threshold below which we don't log/fix (to avoid float noise)
EPSILON = Decimal("0.01")


@dataclass
class ReconciliationResult:
    """Result for a single user reconciliation."""
    user_id: int
    cached_balance: Decimal
    computed_balance: Decimal
    delta: Decimal
    auto_fixed: bool = False


def compute_user_balance(session: Session, user_id: int) -> Decimal:
    """
    Compute the true balance for a user from source of truth.
    
    Formula: SUM(credits_remaining from active lots) - SUM(held credits)
    """
    now = datetime.utcnow()
    
    # Sum of remaining credits in active lots
    lots = session.exec(
        select(CreditLot)
        .where(
            CreditLot.user_id == user_id,
            CreditLot.status == "ACTIVE",
            CreditLot.credits_remaining > 0,
        )
    ).all()
    
    lot_total = Decimal("0")
    for lot in lots:
        # Skip expired lots
        if lot.expires_at and lot.expires_at < now:
            continue
        lot_total += Decimal(str(lot.credits_remaining))
    
    # Sum of held credits
    holds = session.exec(
        select(CreditHold)
        .where(
            CreditHold.user_id == user_id,
            CreditHold.status == "held",
        )
    ).all()
    
    held_total = sum(Decimal(str(h.reserved_credits)) for h in holds)
    
    return lot_total - held_total


def reconcile_user(
    session: Session,
    user: User,
    job_run_id: str,
    autofix: bool = False,
) -> ReconciliationResult:
    """
    Reconcile a single user's cached vs computed balance.
    """
    cached = Decimal(str(user.credits_balance or 0))
    computed = compute_user_balance(session, user.id)
    delta = cached - computed
    
    result = ReconciliationResult(
        user_id=user.id,
        cached_balance=cached,
        computed_balance=computed,
        delta=delta,
    )
    
    if abs(delta) > EPSILON:
        # Log discrepancy
        logger.warning(
            f"[RECONCILIATION] Balance mismatch for user {user.id}: "
            f"cached={cached}, computed={computed}, delta={delta}"
        )
        
        # Create record
        record = ReconciliationRecord(
            user_id=user.id,
            cached_balance=cached,
            computed_balance=computed,
            delta=delta,
            auto_fixed=False,
            job_run_id=job_run_id,
        )
        
        if autofix:
            # Fix the cached balance
            user.credits_balance = float(computed)
            session.add(user)
            result.auto_fixed = True
            record.auto_fixed = True
            logger.info(
                f"[RECONCILIATION] Auto-fixed user {user.id}: "
                f"{cached} -> {computed}"
            )
        
        session.add(record)
    
    return result


def run_nightly_reconciliation() -> Dict:
    """
    Main entry point for nightly reconciliation.
    
    Returns summary stats.
    """
    job_run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    logger.info(f"[RECONCILIATION] Starting job {job_run_id}")
    
    stats = {
        "job_run_id": job_run_id,
        "users_checked": 0,
        "mismatches_found": 0,
        "auto_fixed": 0,
        "errors": 0,
    }
    
    with get_session_context() as session:
        # Get all users with credit balances or lots
        # This could be optimized to only check active users
        users = session.exec(select(User)).all()
        stats["users_checked"] = len(users)
        
        for user in users:
            try:
                result = reconcile_user(
                    session=session,
                    user=user,
                    job_run_id=job_run_id,
                    autofix=RECONCILIATION_AUTOFIX_ENABLED,
                )
                
                if abs(result.delta) > EPSILON:
                    stats["mismatches_found"] += 1
                    if result.auto_fixed:
                        stats["auto_fixed"] += 1
                        
            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"[RECONCILIATION] Error for user {user.id}: {e}"
                )
                log_billing_error(
                    user_id=user.id,
                    error_code="RECONCILIATION_ERROR",
                    error_message=str(e),
                    metadata={"job_run_id": job_run_id},
                )
                inc_billing_error("RECONCILIATION_ERROR")
        
        session.commit()
    
    logger.info(f"[RECONCILIATION] Job complete: {stats}")
    
    # Alert if high mismatch rate
    if stats["users_checked"] > 0:
        mismatch_rate = stats["mismatches_found"] / stats["users_checked"]
        if mismatch_rate > 0.01:  # More than 1% mismatch
            logger.critical(
                f"[RECONCILIATION] HIGH MISMATCH RATE: {mismatch_rate:.2%} "
                f"({stats['mismatches_found']}/{stats['users_checked']})"
            )
    
    return stats


# Celery task wrapper
try:
    from celery import shared_task
    
    @shared_task(name="billing.nightly_reconciliation")
    def nightly_reconciliation_task():
        """Celery task for nightly reconciliation."""
        return run_nightly_reconciliation()
        
except ImportError:
    pass


def expire_stale_holds(max_age_hours: int = 24) -> Dict:
    """
    Expire holds that have been stuck in 'held' status for too long.
    
    This protects against orphaned holds from crashed processes.
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    stats = {"expired_count": 0}
    
    with get_session_context() as session:
        stale_holds = session.exec(
            select(CreditHold)
            .where(
                CreditHold.status == "held",
                CreditHold.created_at < cutoff,
            )
        ).all()
        
        for hold in stale_holds:
            hold.status = "expired"
            hold.finalized_at = datetime.utcnow()
            session.add(hold)
            stats["expired_count"] += 1
            
            logger.warning(
                f"[RECONCILIATION] Expired stale hold {hold.id} "
                f"for user {hold.user_id}, request {hold.request_id}"
            )
        
        session.commit()
    
    return stats
