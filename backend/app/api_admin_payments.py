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
    page_size: int = 25,
    search: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(CreditLot).where(CreditLot.lot_type == "TOPUP")
    
    if search:
        # Search by external_ref or amount_paid
        try:
            val = float(search)
            query = query.where(CreditLot.amount_paid == val)
        except ValueError:
            query = query.where(CreditLot.external_ref.contains(search))
            
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    lots = session.exec(query.order_by(desc(CreditLot.purchased_at)).offset(offset).limit(page_size)).all()
    
    return {"total": total_count, "page": page, "page_size": page_size, "data": lots}

@router.get("/lots")
def list_lots(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
    lot_type: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(CreditLot)
    if user_id:
        query = query.where(CreditLot.user_id == user_id)
    if lot_type:
        query = query.where(CreditLot.lot_type == lot_type)
        
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    lots = session.exec(query.order_by(desc(CreditLot.purchased_at)).offset(offset).limit(page_size)).all()
    
    return {"total": total_count, "page": page, "page_size": page_size, "data": lots}

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
    page_size: int = 25,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    from sqlalchemy import or_
    query = select(RequestEvent)
    
    if model:
        query = query.where(RequestEvent.model == model)
    if provider:
        query = query.where(RequestEvent.provider == provider)
    if status:
        query = query.where(RequestEvent.status == status)
    if user_id:
        query = query.where(RequestEvent.user_id == user_id)
        
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    events = session.exec(query.order_by(desc(RequestEvent.created_at)).offset((page - 1) * page_size).limit(page_size)).all()
    
    # Enrich with Cost Estimate "Live"
    results = []
    for e in events:
        est_cost, price_id = cost_estimation_service.estimate_provider_cost(session, e)
        results.append({
            "request_id": e.request_id,
            "created_at": e.created_at,
            "user_id": e.user_id,
            "provider": e.provider,
            "model": e.model,
            "tokens_in": e.tokens_in,
            "tokens_out": e.tokens_out,
            "cost_stored": e.cost_usd,
            "cost_estimated": est_cost,
            "status": e.status
        })
        
    return {"total": total_count, "data": results, "page": page, "page_size": page_size}

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

# --- Subscription Management ---

from app.models import Subscription, SubscriptionPeriod

@router.get("/subscriptions")
def list_subscriptions(
    page: int = 1,
    page_size: int = 25,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(Subscription)
    if status:
        query = query.where(Subscription.status == status)
        
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    subs = session.exec(query.order_by(desc(Subscription.created_at)).offset(offset).limit(page_size)).all()
    
    # Enrich with current period and plan name
    results = []
    for sub in subs:
        plan = sub.plan
        results.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "plan_name": plan.name if plan else "Unknown",
            "status": sub.status,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "credits_balance": sub.credits_balance,
            "credits_used_this_period": sub.credits_used_this_period,
            "feature_usage": sub.feature_usage,
            "auto_renew": sub.auto_renew
        })
    return {"total": total_count, "page": page, "page_size": page_size, "data": results}

@router.get("/subscriptions/{sub_id}/periods")
def list_subscription_periods(
    sub_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    query = select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub_id).order_by(desc(SubscriptionPeriod.period_start))
    return session.exec(query).all()


# --- Stripe Specific Admin ---

from app.models import StripeEvent, TopUpOrder, SubscriptionBillingLink, SystemErrorEntry

@router.get("/stripe/events")
def list_stripe_events(
    page: int = 1,
    page_size: int = 25,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(StripeEvent)
    if event_type:
        query = query.where(StripeEvent.type == event_type)
    if status:
        query = query.where(StripeEvent.process_status == status)
        
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    events = session.exec(query.order_by(desc(StripeEvent.received_at)).offset(offset).limit(page_size)).all()
    return {"total": total_count, "page": page, "page_size": page_size, "data": events}

@router.post("/stripe/events/{event_id}/replay")
def replay_stripe_event(
    event_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Admin-only replay of a Stripe event for forensic debugging."""
    event = session.exec(select(StripeEvent).where(StripeEvent.stripe_event_id == event_id)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    from app.services.stripe_webhook_processor import stripe_webhook_processor
    stripe_webhook_processor.process_event(session, event)
    return {"status": "replayed", "process_status": event.process_status}

@router.get("/stripe/reconciliation")
def get_reconciliation_errors(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """List issues found by the nightly reconciliation job."""
    query = select(SystemErrorEntry).where(SystemErrorEntry.component == "StripeReconciler").order_by(desc(SystemErrorEntry.created_at))
    return session.exec(query.limit(100)).all()

@router.get("/details/{payment_id}")
def get_payment_detail(
    payment_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Detailed drill-down for a single payment, linking Stripe PI, TopUpOrder, and CreditLot."""
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, detail="Payment not found")
        
    order = None
    if payment.provider == "STRIPE":
        order = session.exec(select(TopUpOrder).where(
            (TopUpOrder.stripe_payment_intent_id == payment.external_id) |
            (TopUpOrder.stripe_checkout_session_id == payment.external_id)
        )).first()
        
    lot = None
    if payment.external_id:
        lot = session.exec(select(CreditLot).where(CreditLot.external_ref == payment.external_id)).first()
        
    return {
        "payment": payment,
        "order": order,
        "lot": lot
    }

@router.get("/subscriptions/{sub_id}/billing")
def get_subscription_billing_detail(
    sub_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Fetch external billing links (Stripe) for a subscription."""
    link = session.exec(select(SubscriptionBillingLink).where(SubscriptionBillingLink.subscription_id == sub_id)).first()
    return {
        "billing_link": link
    }
