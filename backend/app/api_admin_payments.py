from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, desc, func
from datetime import datetime, timedelta

from app.database import get_session
from app.models import User, RequestEvent, ProviderModelPricing, BillingLedger, SolverOutputAttempt
from app.api_admin import get_staff_user, get_admin_user
from app.services.provider_pricing_service import provider_pricing_service
from app.services.cost_estimation_service import cost_estimation_service
from app.services.admin.analytics_service import _calc_cost

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])

# --- Overview ---

@router.get("/overview")
def get_payments_overview(
    range_days: int = 7,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """
    Overview for Phase 0 Dashboard.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=range_days)
    
    # 1. Total Estimated Provider Cost (from RequestEvent)
    # Ideally we'd iterate and sum using cost_estimation_service, but that's slow.
    # We'll rely on stored `cost_usd` if present, else fallback to _calc_cost (legacy) 
    # OR better: do an aggregate query if possible.
    # RequestEvent.cost_usd is populated by `record_request_event`, relying on _calc_cost.
    # So stored cost is "legacy estimate".
    # Phase 0 Goal: Show "Estimated Provider Cost".
    
    events = session.exec(
        select(RequestEvent).where(RequestEvent.created_at >= start_date)
    ).all()
    
    total_provider_cost = 0.0
    total_tokens = 0
    request_count = len(events)
    
    # Simple aggregation loop (can be optimized in SQL later)
    for e in events:
        # Use existing cost if available, else estimate
        c = e.cost_usd
        if c is None:
            # Try new estimator first? No, that requires DB lookup per row (N+1).
            # Fallback to legacy _calc_cost for speed in Phase 0 overview
            c = _calc_cost(e.tokens_total, e.model, e.tokens_in, e.tokens_out)
            
        total_provider_cost += (c or 0.0)
        total_tokens += (e.tokens_total or 0)
        
    # 2. Total User Spend (Credits consumed)
    # Query UsageLedger (DEBIT)
    # user_spend = sum(credits_charged)
    usage_query = select(func.sum(BillingLedger.credits_charged)).where(
        BillingLedger.created_at >= start_date,
        BillingLedger.transaction_type == "DEBIT",
        BillingLedger.status == "SETTLED"
    )
    total_credits_consumed = session.exec(usage_query).one() or 0.0
    
    # Convert credits to approx USD for comparison (assuming $1 = 25 credits standard)
    # This is a rough "Revenue Recognition" metric.
    estimated_revenue = total_credits_consumed / 25.0
    
    return {
        "start_date": start_date,
        "days": range_days,
        "metrics": {
            "provider_cost_usd": round(total_provider_cost, 4),
            "credits_consumed": round(total_credits_consumed, 2),
            "estimated_revenue_usd": round(estimated_revenue, 2),
            "gross_margin_usd": round(estimated_revenue - total_provider_cost, 2),
            "request_count": request_count,
            "total_tokens": total_tokens
        }
    }

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
