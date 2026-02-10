"""
Admin Billing: Ledger Explorer API

Endpoints for querying the billing ledger.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, BillingLedger
from app.admin_billing.deps import get_admin_user

router = APIRouter(prefix="/api/admin/billing/ledger", tags=["admin-billing-ledger"])


class LedgerEntryResponse(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    action_type: Optional[str]
    request_id: Optional[str]
    idempotency_key: Optional[str]
    status: Optional[str]
    credits_charged: Optional[float]
    credits_before: Optional[float]
    credits_after: Optional[float]
    provider_cost_usd: Optional[float]
    tier: Optional[str]
    attempt_id: Optional[str]
    finalized_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedResponse)
async def query_ledger(
    user_id: Optional[int] = None,
    request_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Query billing ledger with filters."""
    query = select(BillingLedger)
    count_query = select(func.count(BillingLedger.id))
    
    if user_id:
        query = query.where(BillingLedger.user_id == user_id)
        count_query = count_query.where(BillingLedger.user_id == user_id)
    
    if request_id:
        query = query.where(BillingLedger.request_id == request_id)
        count_query = count_query.where(BillingLedger.request_id == request_id)
    
    if attempt_id:
        query = query.where(BillingLedger.attempt_id == attempt_id)
        count_query = count_query.where(BillingLedger.attempt_id == attempt_id)
    
    if status:
        query = query.where(BillingLedger.status == status)
        count_query = count_query.where(BillingLedger.status == status)
    
    if action_type:
        query = query.where(BillingLedger.action_type == action_type)
        count_query = count_query.where(BillingLedger.action_type == action_type)
    
    if start_date:
        query = query.where(BillingLedger.created_at >= start_date)
        count_query = count_query.where(BillingLedger.created_at >= start_date)
    
    if end_date:
        query = query.where(BillingLedger.created_at <= end_date)
        count_query = count_query.where(BillingLedger.created_at <= end_date)
    
    total = session.exec(count_query).one()
    entries = session.exec(
        query.order_by(BillingLedger.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    # Get user emails
    user_ids = {e.user_id for e in entries}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all()}
    
    results = []
    for e in entries:
        user = users.get(e.user_id)
        results.append(LedgerEntryResponse(
            id=e.id,
            user_id=e.user_id,
            user_email=user.email if user else None,
            action_type=e.action_type,
            request_id=e.request_id,
            idempotency_key=e.idempotency_key,
            status=e.status,
            credits_charged=float(e.credits_charged) if e.credits_charged else None,
            credits_before=float(e.credits_before) if e.credits_before else None,
            credits_after=float(e.credits_after) if e.credits_after else None,
            provider_cost_usd=float(e.provider_cost_usd) if e.provider_cost_usd else None,
            tier=e.tier,
            attempt_id=e.attempt_id,
            finalized_at=e.finalized_at,
            created_at=e.created_at,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{entry_id}", response_model=LedgerEntryResponse)
async def get_ledger_entry(
    entry_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get a specific ledger entry."""
    entry = session.get(BillingLedger, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    
    user = session.get(User, entry.user_id)
    
    return LedgerEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        user_email=user.email if user else None,
        action_type=entry.action_type,
        request_id=entry.request_id,
        idempotency_key=entry.idempotency_key,
        status=entry.status,
        credits_charged=float(entry.credits_charged) if entry.credits_charged else None,
        credits_before=float(entry.credits_before) if entry.credits_before else None,
        credits_after=float(entry.credits_after) if entry.credits_after else None,
        provider_cost_usd=float(entry.provider_cost_usd) if entry.provider_cost_usd else None,
        tier=entry.tier,
        attempt_id=entry.attempt_id,
        finalized_at=entry.finalized_at,
        created_at=entry.created_at,
    )
