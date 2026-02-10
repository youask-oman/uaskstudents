from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import Session, select, desc, func
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse

from app.database import get_session
from app.models import (
    User,
    RequestEvent,
    BillingLedger,
    CreditLot,
    Payment,
    CreditLotConsumption,
    CreditHold,
    TopUpOrder,
    TopUpProduct,
    StripeEvent,
    Subscription,
    SubscriptionBillingLink,
    Invoice,
    InvoiceLineItem,
    ReconciliationFinding,
    StripePriceMap,
)
from app.api_admin import get_staff_user, get_admin_user
from app.admin_billing.deps import get_superadmin_user
from app.services.cost_estimation_service import cost_estimation_service
from app.services.audit_log_service import audit_log_service
from app.jobs.nightly_reconciliation import compute_user_balance
from app.config import get_settings
import stripe

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])

@router.get("/overview")
def get_payments_overview(
    range_days: int = 30,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    """
    Payments & Credits overview for admin dashboard.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=range_days)

    # Provider cost & request volume
    events = session.exec(
        select(RequestEvent).where(RequestEvent.created_at >= start_date)
    ).all()
    total_provider_cost = sum([float(e.cost_usd or 0.0) for e in events])
    total_tokens = sum([int(e.tokens_total or 0) for e in events])
    request_count = len(events)

    # Credits consumed (ledger debits)
    credits_consumed = session.exec(
        select(func.sum(CreditLotConsumption.amount))
        .where(CreditLotConsumption.created_at >= start_date)
        .where(CreditLotConsumption.direction == "DEBIT")
    ).one()
    total_credits_consumed = float(credits_consumed or 0)

    # Credits minted (topups)
    credits_minted = session.exec(
        select(func.sum(CreditLot.credits_total))
        .where(CreditLot.purchased_at >= start_date)
        .where(CreditLot.lot_type == "TOPUP")
    ).one()
    total_credits_minted = float(credits_minted or 0)

    # Stripe payments
    payments = session.exec(
        select(Payment)
        .where(Payment.created_at >= start_date)
        .where(Payment.provider == "STRIPE")
    ).all()
    successful_payments = [p for p in payments if p.status.upper() in {"SUCCEEDED", "COMPLETED"}]
    failed_payments = [p for p in payments if p.status.upper() in {"FAILED", "CANCELED"}]
    refunded_payments = [p for p in payments if p.status.upper() == "REFUNDED"]
    gross_revenue = sum([float(p.amount or 0) for p in successful_payments])
    refunds_total = sum([float(p.amount or 0) for p in refunded_payments])

    # Outstanding holds
    holds = session.exec(
        select(CreditHold).where(CreditHold.status == "held")
    ).all()
    outstanding_holds = sum([float(h.reserved_credits or 0) for h in holds])

    return {
        "start_date": start_date,
        "days": range_days,
        "metrics": {
            "provider_cost_usd": round(total_provider_cost, 4),
            "credits_consumed": round(total_credits_consumed, 2),
            "credits_minted": round(total_credits_minted, 2),
            "stripe_revenue_gross_usd": round(gross_revenue, 2),
            "refunds_total_usd": round(refunds_total, 2),
            "successful_payments": len(successful_payments),
            "failed_payments": len(failed_payments),
            "request_count": request_count,
            "total_tokens": total_tokens,
            "outstanding_hold_credits": round(outstanding_holds, 2),
        },
    }

@router.get("/topups")
def list_topups(
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    """
    Completed top-ups with CreditLot + ledger linkage.
    """
    offset = (page - 1) * page_size
    query = select(TopUpOrder).order_by(desc(TopUpOrder.created_at))
    count_stmt = select(func.count(TopUpOrder.id))

    if search:
        query = query.where(
            (TopUpOrder.stripe_payment_intent_id.contains(search))
            | (TopUpOrder.stripe_checkout_session_id.contains(search))
        )
        count_stmt = count_stmt.where(
            (TopUpOrder.stripe_payment_intent_id.contains(search))
            | (TopUpOrder.stripe_checkout_session_id.contains(search))
        )

    total_count = session.exec(count_stmt).one()
    orders = session.exec(query.offset(offset).limit(page_size)).all()

    user_ids = {o.user_id for o in orders}
    users = {}
    if user_ids:
        users = {
            u.id: u
            for u in session.exec(select(User).where(User.id.in_(list(user_ids)))).all()
        }

    product_ids = {o.topup_product_id for o in orders}
    products = {}
    if product_ids:
        products = {
            p.id: p
            for p in session.exec(select(TopUpProduct).where(TopUpProduct.id.in_(list(product_ids)))).all()
        }

    results = []
    for o in orders:
        user_obj = users.get(o.user_id)
        product = products.get(o.topup_product_id)
        results.append(
            {
                "id": o.id,
                "created_at": o.created_at,
                "user_id": o.user_id,
                "user_email": user_obj.email if user_obj else None,
                "status": o.status,
                "credits": o.credits,
                "price_usd": o.price_usd,
                "currency": o.currency,
                "product_code": product.code if product else None,
                "product_name": product.name if product else None,
                "stripe_payment_intent_id": o.stripe_payment_intent_id,
                "stripe_checkout_session_id": o.stripe_checkout_session_id,
                "credit_lot_id": o.fulfill_credit_lot_id,
                "ledger_id": o.fulfill_usage_ledger_id,
            }
        )

    return {"total": total_count, "page": page, "page_size": page_size, "data": results}


@router.get("/topups/{topup_id}")
def get_topup_detail(
    topup_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    order = session.get(TopUpOrder, topup_id)
    if not order:
        raise HTTPException(status_code=404, detail="Top-up not found")

    payment = None
    if order.stripe_payment_intent_id:
        payment = session.exec(
            select(Payment)
            .where(Payment.external_id == order.stripe_payment_intent_id)
            .where(Payment.provider == "STRIPE")
        ).first()

    lot = None
    if order.fulfill_credit_lot_id:
        lot = session.get(CreditLot, order.fulfill_credit_lot_id)

    return {
        "topup": order,
        "payment": payment,
        "credit_lot": lot,
    }

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
        
    count_stmt = select(func.count(CreditLot.id))
    if user_id: count_stmt = count_stmt.where(CreditLot.user_id == user_id)
    if lot_type: count_stmt = count_stmt.where(CreditLot.lot_type == lot_type)
    total_count = session.exec(count_stmt).one()
    lots = session.exec(query.order_by(desc(CreditLot.purchased_at)).offset(offset).limit(page_size)).all()
    
    return {"total": total_count, "page": page, "page_size": page_size, "data": lots}

@router.get("/consumption/{request_id}")
def get_consumption_drilldown(
    request_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    # Link: request_id (reference_id) -> UsageLedger -> CreditLotConsumption
    # Phase 1: request_id -> BillingLedger
    from app.models import UsageLedger, BillingLedger, CreditLotConsumption
    
    results = []
    
    # 1. Check BillingLedger (New System)
    b_entry = session.exec(select(BillingLedger).where(BillingLedger.request_id == request_id)).first()
    if b_entry:
        # Check for consumption linked to this billing ledger (if any)
        # Assuming we might link them later, but for now just show the ledger
        results.append({
            "usage_ledger": {
                "id": b_entry.id,
                "amount": b_entry.credits_charged,
                "transaction_type": "DEBIT",
                "created_at": b_entry.created_at,
                "reference_id": b_entry.request_id
            },
            "lot_allocations": [] 
        })
        
    # 2. Check UsageLedger (Legacy / Subscription)
    # Some older requests might use UsageLedger
    u_entries = session.exec(select(UsageLedger).where(UsageLedger.reference_id == request_id)).all()
    
    for u in u_entries:
        consumptions = session.exec(select(CreditLotConsumption).where(
            CreditLotConsumption.usage_ledger_id == u.id
        )).all()
        # Avoid duplicate if matches BillingLedger ID (unlikely)
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
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    """
    Payment requests created by the app (TopUpOrder).
    """
    offset = (page - 1) * page_size
    query = select(TopUpOrder).order_by(desc(TopUpOrder.created_at))
    count_stmt = select(func.count(TopUpOrder.id))

    if status:
        query = query.where(TopUpOrder.status == status)
        count_stmt = count_stmt.where(TopUpOrder.status == status)
    if user_id:
        query = query.where(TopUpOrder.user_id == user_id)
        count_stmt = count_stmt.where(TopUpOrder.user_id == user_id)

    total_count = session.exec(count_stmt).one()
    orders = session.exec(query.offset(offset).limit(page_size)).all()

    # Map product info
    product_ids = {o.topup_product_id for o in orders}
    products = {}
    if product_ids:
        products = {
            p.id: p
            for p in session.exec(select(TopUpProduct).where(TopUpProduct.id.in_(list(product_ids)))).all()
        }

    results = []
    for o in orders:
        product = products.get(o.topup_product_id)
        results.append(
            {
                "id": o.id,
                "created_at": o.created_at,
                "user_id": o.user_id,
                "status": o.status,
                "product_code": product.code if product else None,
                "product_name": product.name if product else None,
                "credits": o.credits,
                "price_usd": o.price_usd,
                "currency": o.currency,
                "stripe_checkout_session_id": o.stripe_checkout_session_id,
                "stripe_payment_intent_id": o.stripe_payment_intent_id,
                "credit_lot_id": o.fulfill_credit_lot_id,
            }
        )

    return {"total": total_count, "data": results, "page": page, "page_size": page_size}

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
        
    count_stmt = select(func.count(Subscription.id))
    if status: count_stmt = count_stmt.where(Subscription.status == status)
    total_count = session.exec(count_stmt).one()
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

from app.models import StripeEvent, TopUpOrder, SubscriptionBillingLink


@router.get("/stripe/health")
def stripe_health(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        return {
            "ok": False,
            "mode": "unknown",
            "account_id": None,
            "api_version": None,
            "last_error": "STRIPE_SECRET_KEY not set",
        }

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        account = stripe.Account.retrieve()
        livemode = bool(getattr(account, "livemode", False))
        return {
            "ok": True,
            "mode": "live" if livemode else "test",
            "account_id": getattr(account, "id", None),
            "api_version": getattr(account, "settings", {}).get("api_version") if hasattr(account, "settings") else None,
            "last_error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": "unknown",
            "account_id": None,
            "api_version": None,
            "last_error": str(e),
        }

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
        
    count_stmt = select(func.count(StripeEvent.id))
    if event_type: count_stmt = count_stmt.where(StripeEvent.type == event_type)
    if status: count_stmt = count_stmt.where(StripeEvent.process_status == status)
    total_count = session.exec(count_stmt).one()
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

@router.get("/reconciliation")
def get_reconciliation_report(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    """
    Dry-run reconciliation report for money ↔ credits ↔ usage.
    """
    # 1) Stripe payments without local Payment rows
    missing_payment_rows = session.exec(
        select(StripeEvent)
        .where(StripeEvent.type == "payment_intent.succeeded")
        .order_by(desc(StripeEvent.received_at))
        .limit(100)
    ).all()
    missing_payment_ids = []
    for evt in missing_payment_rows:
        pi_id = evt.payload_json.get("data", {}).get("object", {}).get("id")
        if not pi_id:
            continue
        payment = session.exec(
            select(Payment)
            .where(Payment.external_id == pi_id)
            .where(Payment.provider == "STRIPE")
        ).first()
        if not payment:
            missing_payment_ids.append(pi_id)

    # 2) Paid orders missing credit lots
    paid_orders = session.exec(
        select(TopUpOrder).where(TopUpOrder.status == "FULFILLED")
    ).all()
    missing_credit_lots = [o.id for o in paid_orders if not o.fulfill_credit_lot_id]

    # 3) Duplicate credit lots by external_ref
    dup_rows = session.exec(
        select(CreditLot.external_ref, func.count(CreditLot.id))
        .where(CreditLot.external_ref != None)
        .group_by(CreditLot.external_ref)
        .having(func.count(CreditLot.id) > 1)
    ).all()
    duplicate_credit_lots = [{"external_ref": r[0], "count": r[1]} for r in dup_rows]

    # 4) Mismatched pack amounts
    mismatched_pack_amounts = []
    for order in paid_orders:
        if not order.fulfill_credit_lot_id:
            continue
        lot = session.get(CreditLot, order.fulfill_credit_lot_id)
        if not lot:
            continue
        if float(lot.credits_total or 0) != float(order.credits or 0):
            mismatched_pack_amounts.append(
                {"topup_order_id": order.id, "order_credits": float(order.credits or 0), "lot_credits": float(lot.credits_total or 0)}
            )

    # 5) Orphan ledger events
    orphan_ledger = session.exec(
        select(BillingLedger)
        .where(BillingLedger.action_type == "TOPUP")
        .where(BillingLedger.request_id == None)
    ).all()

    # 6) Stale holds
    stale_holds = session.exec(
        select(CreditHold)
        .where(CreditHold.status == "held")
        .where(CreditHold.created_at <= datetime.utcnow() - timedelta(hours=2))
    ).all()

    return {
        "missing_payment_rows": missing_payment_ids,
        "missing_credit_lots_for_paid_orders": missing_credit_lots,
        "duplicate_credit_lots": duplicate_credit_lots,
        "mismatched_pack_amounts": mismatched_pack_amounts,
        "orphan_ledger_events": [l.id for l in orphan_ledger],
        "stale_holds": [h.id for h in stale_holds],
    }


@router.post("/reconciliation/run")
def run_reconciliation(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_superadmin_user),
):
    """
    Superadmin-only reconciliation run (confirmation required).
    """
    confirm = payload.get("confirm")
    reason = payload.get("reason") or ""
    if confirm != "RUN_RECONCILIATION":
        raise HTTPException(status_code=400, detail="Confirmation failed. Pass confirm=RUN_RECONCILIATION")
    if not reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    audit_log_service.log_action(
        session=session,
        admin_user_id=user.id,
        action="EXECUTE",
        entity_type="PAYMENTS_RECONCILIATION",
        entity_id="run",
        before_json={"confirm": confirm},
        after_json={"status": "triggered"},
        reason=reason or "Admin-triggered reconciliation",
        request=request,
    )
    session.commit()

    # For now we only return dry-run output
    return {"status": "ok", "message": "Reconciliation triggered", "confirm": confirm}

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


# --- Invoicing ---

from app.models import Invoice, InvoiceLineItem

@router.get("/invoices")
def list_invoices(
    page: int = 1,
    page_size: int = 25,
    user_id: Optional[int] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    offset = (page - 1) * page_size
    query = select(Invoice)
    if user_id:
        query = query.where(Invoice.user_id == user_id)
    if kind:
        query = query.where(Invoice.kind == kind)
    if status:
        query = query.where(Invoice.status == status)
        
    count_stmt = select(func.count(Invoice.id))
    if user_id: count_stmt = count_stmt.where(Invoice.user_id == user_id)
    if kind: count_stmt = count_stmt.where(Invoice.kind == kind)
    if status: count_stmt = count_stmt.where(Invoice.status == status)
    total_count = session.exec(count_stmt).one()
    invoices = session.exec(query.order_by(desc(Invoice.created_at)).offset(offset).limit(page_size)).all()
    return {"total": total_count, "page": page, "page_size": page_size, "data": invoices}

@router.get("/invoices/{invoice_id}")
def get_invoice_detail(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, detail="Invoice not found")
        
    lines = session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)).all()
    return {
        "invoice": invoice,
        "lines": lines
    }

@router.get("/invoices/{invoice_id}/html")
def get_invoice_html(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    from app.services.invoice_service import invoice_service
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(404, detail="Invoice not found")
    
    invoice_user = session.get(User, invoice.user_id)
    lines = session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)).all()
    
    user_name = invoice_user.full_name if invoice_user else f"User #{invoice.user_id}"
    user_email = invoice_user.email if invoice_user else "---"

    html = invoice_service.render_invoice_html(invoice, lines, user_name, user_email)
    return StreamingResponse(iter([html]), media_type="text/html")
