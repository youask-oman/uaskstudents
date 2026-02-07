from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select, desc, func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.database import get_session, engine
from app.models import (
    User, ReconciliationFinding, SystemErrorEntry, StripeEvent, CreditHold
)
from app.api_admin import get_staff_user, get_admin_user
from sqlalchemy import inspect
import logging

router = APIRouter(prefix="/api/admin/health", tags=["admin-health"])
logger = logging.getLogger("admin_health")

@router.get("/db")
def get_db_health(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Database health check endpoint."""
    try:
        # Connection test
        session.exec(select(func.count(User.id))).one()
        connection_ok = True
    except Exception as e:
        connection_ok = False
        logger.error(f"DB connection failed: {e}")
    
    # Get table sizes (approximate)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    table_sizes = {}
    for table in table_names[:20]:  # Limit to first 20 tables
        try:
            count = session.exec(select(func.count()).select_from(table)).one()
            table_sizes[table] = count
        except:
            table_sizes[table] = "N/A"
    
    return {
        "connection_ok": connection_ok,
        "timestamp": datetime.utcnow().isoformat(),
        "table_count": len(table_names),
        "sample_table_sizes": table_sizes
    }

@router.get("/findings")
def list_findings(
    status: Optional[str] = "OPEN",
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """List reconciliation findings."""
    query = select(ReconciliationFinding)
    
    if status:
        query = query.where(ReconciliationFinding.status == status)
    if severity:
        query = query.where(ReconciliationFinding.severity == severity)
    
    # Count
    count_stmt = select(func.count(ReconciliationFinding.id))
    if status: count_stmt = count_stmt.where(ReconciliationFinding.status == status)
    if severity: count_stmt = count_stmt.where(ReconciliationFinding.severity == severity)
    total_count = session.exec(count_stmt).one()
    
    # Fetch
    findings = session.exec(
        query.order_by(desc(ReconciliationFinding.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    
    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "data": findings
    }

@router.post("/findings/{finding_id}/resolve")
def resolve_finding(
    finding_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Mark a finding as resolved."""
    finding = session.get(ReconciliationFinding, finding_id)
    if not finding:
        raise HTTPException(404, detail="Finding not found")
    
    finding.status = "RESOLVED"
    finding.resolved_at = datetime.utcnow()
    finding.resolved_by = user.id
    
    session.add(finding)
    session.commit()
    
    return {"status": "resolved", "finding": finding}

@router.get("/errors")
def list_errors(
    severity: Optional[str] = None,
    error_code: Optional[str] = None,
    component: Optional[str] = None,
    hours: int = 24,
    page: int = 1,
    page_size: int = 25,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """List system errors with filtering."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    query = select(SystemErrorEntry).where(SystemErrorEntry.created_at >= cutoff)
    
    if severity:
        query = query.where(SystemErrorEntry.severity == severity)
    if error_code:
        query = query.where(SystemErrorEntry.error_code == error_code)
    if component:
        query = query.where(SystemErrorEntry.component == component)
    
    # Count
    count_stmt = select(func.count(SystemErrorEntry.id)).where(SystemErrorEntry.created_at >= cutoff)
    if severity: count_stmt = count_stmt.where(SystemErrorEntry.severity == severity)
    if error_code: count_stmt = count_stmt.where(SystemErrorEntry.error_code == error_code)
    if component: count_stmt = count_stmt.where(SystemErrorEntry.component == component)
    total_count = session.exec(count_stmt).one()
    
    # Fetch
    errors = session.exec(
        query.order_by(desc(SystemErrorEntry.last_seen_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    
    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "hours": hours,
        "data": errors
    }

@router.get("/errors/summary")
def get_error_summary(
    hours: int = 24,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get error summary by code and severity."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Group by error_code
    by_code = session.exec(
        select(
            SystemErrorEntry.error_code,
            func.count(SystemErrorEntry.id).label("count"),
            func.sum(SystemErrorEntry.occurrence_count).label("total_occurrences")
        )
        .where(SystemErrorEntry.created_at >= cutoff)
        .group_by(SystemErrorEntry.error_code)
        .order_by(desc("total_occurrences"))
        .limit(10)
    ).all()
    
    # Group by severity
    by_severity = session.exec(
        select(
            SystemErrorEntry.severity,
            func.count(SystemErrorEntry.id).label("count")
        )
        .where(SystemErrorEntry.created_at >= cutoff)
        .group_by(SystemErrorEntry.severity)
    ).all()
    
    return {
        "hours": hours,
        "by_error_code": [
            {"error_code": code or "UNKNOWN", "unique_errors": count, "total_occurrences": occ or count}
            for code, count, occ in by_code
        ],
        "by_severity": [
            {"severity": sev, "count": count}
            for sev, count in by_severity
        ]
    }

@router.get("/stripe/failed")
def get_failed_stripe_events(
    page: int = 1,
    page_size: int = 25,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """List failed Stripe event processing."""
    query = select(StripeEvent).where(StripeEvent.process_status == "FAILED")
    
    total_count = session.exec(select(func.count(StripeEvent.id)).where(StripeEvent.process_status == "FAILED")).one()
    
    events = session.exec(
        query.order_by(desc(StripeEvent.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    
    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "data": events
    }

@router.get("/holds/stuck")
def get_stuck_holds(
    threshold_minutes: int = 30,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get credit holds stuck in HELD status."""
    threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)
    
    stuck = session.exec(
        select(CreditHold).where(
            CreditHold.status == "HELD",
            CreditHold.created_at < threshold_time
        )
    ).all()
    
    return {
        "threshold_minutes": threshold_minutes,
        "stuck_count": len(stuck),
        "holds": stuck
    }

@router.post("/reconcile/ledgers")
def trigger_ledger_reconciliation(
    subscription_ids: Optional[List[int]] = Body(None),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Manually trigger ledger reconciliation job."""
    from scripts.reconcile_ledgers_job import LedgerReconciliationJob
    
    job = LedgerReconciliationJob(session)
    result = job.run(subscription_ids=subscription_ids)
    
    return result

@router.post("/reconcile/invoices")
def trigger_invoice_reconciliation(
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Manually trigger invoice reconciliation job."""
    from scripts.reconcile_invoices_job import InvoiceReconciliationJob
    
    job = InvoiceReconciliationJob(session)
    result = job.run()
    
    return result

@router.post("/cleanup/holds")
def trigger_hold_cleanup(
    threshold_minutes: int = 30,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Manually trigger credit hold cleanup job."""
    from scripts.cleanup_stale_credit_holds_job import CreditHoldCleanupJob
    
    job = CreditHoldCleanupJob(session, threshold_minutes=threshold_minutes)
    result = job.run()
    
    return result
