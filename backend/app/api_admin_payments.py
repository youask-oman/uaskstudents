from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, desc, func
from datetime import datetime, timedelta

from app.database import get_session
from app.models import User, RequestEvent, ProviderModelPricing, BillingLedger, SolverOutputAttempt, CreditLot, Payment, CreditLotConsumption
from app.api_admin import get_staff_user, get_admin_user
from app.services.provider_pricing_service import provider_pricing_service
from app.services.cost_estimation_service import cost_estimation_service

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])

@router.get("/overview")
def get_payments_overview(
    range_days: int = 7,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """
    Overview for Phase 2 Dashboard.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=range_days)
    
    # 1. Total Estimated Provider Cost
    events = session.exec(select(RequestEvent).where(RequestEvent.created_at >= start_date)).all()
    total_provider_cost = sum([e.cost_usd or 0.0 for e in events])
    total_tokens = sum([e.tokens_total or 0 for e in events])
    request_count = len(events)
    
    # 2. Total User Spend (Credits consumed form BillingLedger)
    # Status: 'SETTLED' (legacy) or 'CHARGED' (Phase 1)
    # Removing transaction_type check as BillingLedger structure changed or was misunderstood.
    usage_query = select(func.sum(BillingLedger.credits_charged)).where(
        BillingLedger.created_at >= start_date,
        BillingLedger.status.in_(["SETTLED", "CHARGED"])
    )
    total_credits_consumed = session.exec(usage_query).one() or 0.0
    
    # 3. Top-Up Revenue (Real $)
    # Workaround: Sum valid CreditLots (TOPUP) purchased_at >= start_date
    topup_revenue_query = select(func.sum(CreditLot.amount_paid)).where(
        CreditLot.purchased_at >= start_date,
        CreditLot.lot_type == "TOPUP"
    )
    total_revenue_usd = session.exec(topup_revenue_query).one() or 0.0
    
    return {
        "start_date": start_date,
        "days": range_days,
        "metrics": {
            "provider_cost_usd": round(total_provider_cost, 4),
            "credits_consumed": round(total_credits_consumed, 2),
            "revenue_usd": round(total_revenue_usd, 2),
            "gross_margin_usd": round(total_revenue_usd - total_provider_cost, 2),
            "request_count": request_count,
            "total_tokens": total_tokens
        }
    }

@router.get("/topups")
def list_topups(
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(CreditLot).where(CreditLot.lot_type == "TOPUP").order_by(desc(CreditLot.purchased_at))
    lots = session.exec(query.offset(offset).limit(page_size)).all()
    return lots

@router.get("/lots")
def list_lots(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(CreditLot).order_by(desc(CreditLot.purchased_at))
    if user_id:
        query = query.where(CreditLot.user_id == user_id)
        
    lots = session.exec(query.offset(offset).limit(page_size)).all()
    return lots

@router.get("/consumption/{request_id}")
def get_consumption_drilldown(
    request_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    # Link: request_id (reference_id) -> UsageLedger -> CreditLotConsumption
    from app.models import UsageLedger
    u_entries = session.exec(select(UsageLedger).where(UsageLedger.reference_id == request_id)).all()
    
    results = []
    for u in u_entries:
        consumptions = session.exec(select(CreditLotConsumption).where(
            CreditLotConsumption.usage_ledger_id == u.id
        )).all()
        results.append({
            "usage_ledger": u,
            "lot_allocations": consumptions
        })
        
    return results

# --- Requests Explorer ---

@router.get("/requests")
def list_requests(
    page: int = 1,
    page_size: int = 50,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    query = select(RequestEvent).order_by(desc(RequestEvent.created_at))
    
    if model:
        query = query.where(RequestEvent.model == model)
    if provider:
        query = query.where(RequestEvent.provider == provider)
        
    offset = (page - 1) * page_size
    events = session.exec(query.offset(offset).limit(page_size)).all()
    
    # Enrich with Cost Estimate "Live"
    results = []
    for e in events:
        est_cost, price_id = cost_estimation_service.estimate_provider_cost(session, e)
        
        # Use stored if reasonable, or override with new estimate?
        # Dashboard should show "Stored vs Estimated" maybe?
        # Let's show Estimated based on current Pricing Config for audit
        
        results.append({
            "request_id": e.request_id,
            "created_at": e.created_at,
            "user_id": e.user_id,
            "provider": e.provider,
            "model": e.model,
            "tokens_in": e.tokens_in,
            "tokens_out": e.tokens_out,
            "cost_stored": e.cost_usd,
            "cost_estimated": est_cost, # The Phase 0 value
            "status": e.status
        })
        
    return {"data": results, "page": page, "page_size": page_size}

# --- Pricing Config ---

@router.get("/pricing")
def list_pricing_config(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """List all pricing history"""
    return provider_pricing_service.list_pricing_history(session)

@router.post("/pricing")
def add_pricing_config(
    provider: str,
    model: str,
    price_in: float,
    price_out: float,
    cache_read: float = 0.0,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Add a new pricing version (terminates old one)"""
    new_entry = provider_pricing_service.update_price(
        session,
        provider,
        model,
        price_in,
        price_out,
        cache_read,
        admin_user_id=user.id
    )
    return new_entry
