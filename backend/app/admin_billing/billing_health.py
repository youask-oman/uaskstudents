"""
Admin Billing: Health & Reconciliation API

Endpoints for monitoring billing health and running reconciliation.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
import csv
import io

from app.database import get_session
from app.models import User, CreditHold, BillingLedger
from app.models.credit_program_models import ReconciliationRecord
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service
from app.jobs.nightly_reconciliation import reconcile_user, compute_user_balance

router = APIRouter(prefix="/api/admin/billing/health", tags=["admin-billing-health"])


class HealthDashboard(BaseModel):
    mismatch_count_today: int
    mismatch_count_7d: int
    stuck_holds_count: int
    stuck_holds_p95_age: int
    billing_errors_24h: int
    autofix_enabled: bool


class MismatchEntry(BaseModel):
    user_id: int
    user_email: Optional[str]
    cached_balance: float
    computed_balance: float
    delta: float
    last_fix_time: Optional[datetime]


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=HealthDashboard)
async def get_health_dashboard(
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get billing health dashboard stats."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(hours=24)
    
    # Mismatch counts
    mismatch_today = session.exec(
        select(func.count(ReconciliationRecord.id))
        .where(ReconciliationRecord.created_at >= today_start)
        .where(ReconciliationRecord.delta != 0)
    ).one()
    
    mismatch_7d = session.exec(
        select(func.count(ReconciliationRecord.id))
        .where(ReconciliationRecord.created_at >= week_ago)
        .where(ReconciliationRecord.delta != 0)
    ).one()
    
    # Stuck holds
    active_holds = session.exec(
        select(CreditHold).where(CreditHold.status == "held")
    ).all()
    
    stuck_count = 0
    ages = []
    for h in active_holds:
        age = int((now - h.created_at).total_seconds())
        ages.append(age)
        if age > 3600:  # > 1 hour
            stuck_count += 1
    
    p95_age = sorted(ages)[int(len(ages) * 0.95)] if ages else 0
    
    # Billing errors (from ledger with error status)
    error_count = session.exec(
        select(func.count(BillingLedger.id))
        .where(BillingLedger.created_at >= day_ago)
        .where(BillingLedger.status.in_(["ERROR", "FAILED"]))
    ).one()
    
    # Autofix status
    from app.services.billing_feature_flags import is_reconciliation_autofix_enabled
    autofix_enabled = is_reconciliation_autofix_enabled()
    
    return HealthDashboard(
        mismatch_count_today=mismatch_today,
        mismatch_count_7d=mismatch_7d,
        stuck_holds_count=stuck_count,
        stuck_holds_p95_age=p95_age,
        billing_errors_24h=error_count,
        autofix_enabled=autofix_enabled,
    )


@router.get("/mismatches", response_model=PaginatedResponse)
async def list_mismatches(
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List users with balance mismatches (live check)."""
    # Get users with credit activity
    users = session.exec(
        select(User)
        .where(User.credits_balance != None)
        .where(User.credits_balance != 0)
        .offset(offset)
        .limit(limit)
    ).all()
    
    total = session.exec(
        select(func.count(User.id))
        .where(User.credits_balance != None)
        .where(User.credits_balance != 0)
    ).one()
    
    mismatches = []
    for user in users:
        cached = Decimal(str(user.credits_balance or 0))
        computed = compute_user_balance(session, user.id)
        delta = cached - computed
        
        if abs(delta) > Decimal("0.01"):  # Only show significant mismatches
            # Get last fix time
            last_record = session.exec(
                select(ReconciliationRecord)
                .where(ReconciliationRecord.user_id == user.id)
                .where(ReconciliationRecord.auto_fixed == True)
                .order_by(ReconciliationRecord.created_at.desc())
                .limit(1)
            ).first()
            
            mismatches.append(MismatchEntry(
                user_id=user.id,
                user_email=user.email,
                cached_balance=float(cached),
                computed_balance=float(computed),
                delta=float(delta),
                last_fix_time=last_record.created_at if last_record else None,
            ))
    
    return PaginatedResponse(items=mismatches, total=len(mismatches), limit=limit, offset=offset)


@router.post("/run-reconciliation")
async def run_reconciliation(
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Trigger reconciliation job for all users."""
    from app.jobs.nightly_reconciliation import run_nightly_reconciliation
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="RECONCILIATION_JOB",
        reason="Admin triggered reconciliation",
        request=request,
    )
    session.commit()
    
    # Run synchronously for now (in production, queue as background task)
    stats = run_nightly_reconciliation()
    
    return {
        "success": True,
        "stats": stats,
    }


@router.get("/export")
async def export_mismatches(
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Export mismatches as CSV."""
    # Get all users with balances
    users = session.exec(
        select(User)
        .where(User.credits_balance != None)
        .where(User.credits_balance != 0)
    ).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "email", "cached_balance", "computed_balance", "delta"])
    
    for user in users:
        cached = Decimal(str(user.credits_balance or 0))
        computed = compute_user_balance(session, user.id)
        delta = cached - computed
        
        if abs(delta) > Decimal("0.01"):
            writer.writerow([user.id, user.email, float(cached), float(computed), float(delta)])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mismatches.csv"}
    )
