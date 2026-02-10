"""
Admin Billing: Refund Center API

Endpoints for creating and managing refunds.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, CreditLot, BillingLedger
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service
from app.jobs.nightly_reconciliation import compute_user_balance
from app.services.refund_service import refund_service
from app.admin_billing.billing_wallet import _build_wallet_summary

router = APIRouter(prefix="/api/admin/billing/refunds", tags=["admin-billing-refunds"])


class CreateRefundRequest(BaseModel):
    user_id: int
    credits: float
    reason_code: str  # SERVICE_ISSUE, PAYMENT_REVERSAL, ADMIN_ADJUSTMENT
    reason: str
    source_attempt_id: Optional[str] = None
    source_payment_id: Optional[str] = None
    expires_days: int = 30
    idempotency_key: Optional[str] = None


class RefundResponse(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    credits: float
    reason_code: Optional[str]
    source_attempt_id: Optional[str]
    source_payment_id: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    ledger_id: Optional[int] = None
    wallet_summary: Optional[dict] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedResponse)
async def list_refunds(
    user_id: Optional[int] = None,
    reason_code: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List refund lots."""
    query = select(CreditLot).where(CreditLot.lot_type == "REFUND")
    count_query = select(func.count(CreditLot.id)).where(CreditLot.lot_type == "REFUND")
    
    if user_id:
        query = query.where(CreditLot.user_id == user_id)
        count_query = count_query.where(CreditLot.user_id == user_id)
    
    if reason_code:
        query = query.where(CreditLot.reason_code == reason_code)
        count_query = count_query.where(CreditLot.reason_code == reason_code)
    
    if start_date:
        query = query.where(CreditLot.purchased_at >= start_date)
        count_query = count_query.where(CreditLot.purchased_at >= start_date)
    
    if end_date:
        query = query.where(CreditLot.purchased_at <= end_date)
        count_query = count_query.where(CreditLot.purchased_at <= end_date)
    
    total = session.exec(count_query).one()
    lots = session.exec(
        query.order_by(CreditLot.purchased_at.desc()).offset(offset).limit(limit)
    ).all()
    
    # Get user emails
    user_ids = {lot.user_id for lot in lots}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all()}
    
    results = []
    for lot in lots:
        user = users.get(lot.user_id)
        results.append(RefundResponse(
            id=lot.id,
            user_id=lot.user_id,
            user_email=user.email if user else None,
            credits=float(lot.credits_total) if lot.credits_total else 0,
            reason_code=lot.reason_code,
            source_attempt_id=lot.source_attempt_id,
            source_payment_id=lot.source_payment_id,
            expires_at=lot.expires_at,
            created_at=lot.purchased_at,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.post("", response_model=RefundResponse)
async def create_refund(
    body: CreateRefundRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Create a refund. Requires superadmin."""
    user = session.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.credits <= 0:
        raise HTTPException(status_code=400, detail="credits must be > 0")

    if body.idempotency_key:
        existing_ledger = session.exec(
            select(BillingLedger).where(BillingLedger.idempotency_key == body.idempotency_key)
        ).first()
        if existing_ledger:
            existing_lot = session.exec(
                select(CreditLot)
                .where(CreditLot.lot_type == "REFUND")
                .where(CreditLot.external_ref == body.idempotency_key)
                .where(CreditLot.user_id == body.user_id)
            ).first()
            summary = _build_wallet_summary(session, user)
            return RefundResponse(
                id=existing_lot.id if existing_lot else existing_ledger.id,
                user_id=body.user_id,
                user_email=user.email,
                credits=float(existing_lot.credits_total) if existing_lot else float(body.credits),
                reason_code=existing_lot.reason_code if existing_lot else body.reason_code,
                source_attempt_id=existing_lot.source_attempt_id if existing_lot else body.source_attempt_id,
                source_payment_id=existing_lot.source_payment_id if existing_lot else body.source_payment_id,
                expires_at=existing_lot.expires_at if existing_lot else None,
                created_at=existing_lot.purchased_at if existing_lot else existing_ledger.created_at,
                ledger_id=existing_ledger.id,
                wallet_summary=summary.dict(),
            )

    computed_before = compute_user_balance(session, body.user_id)
    cached_before = Decimal(str(user.credits_balance or 0))

    refund_id = body.idempotency_key or f"admin_refund_{body.user_id}_{int(datetime.utcnow().timestamp())}"
    lot = refund_service.create_refund(
        session=session,
        user_id=body.user_id,
        credits=Decimal(str(body.credits)),
        refund_id=refund_id,
        reason_code=body.reason_code,
        source_payment_id=body.source_payment_id,
        source_attempt_id=body.source_attempt_id,
        is_topup_reversal=False,
    )
    session.flush()

    computed_after = compute_user_balance(session, body.user_id)

    ledger = BillingLedger(
        user_id=body.user_id,
        action_type="ADMIN_REFUND",
        request_id=body.source_attempt_id or body.source_payment_id,
        idempotency_key=body.idempotency_key,
        status="SETTLED",
        credits_charged=Decimal("0"),
        estimated_credits=Decimal("0"),
        actual_credits=Decimal("0"),
        delta_credits=Decimal(str(body.credits)),
        credits_before=Decimal(str(computed_before)),
        credits_after=Decimal(str(computed_after)),
    )
    session.add(ledger)
    session.flush()

    user.credits_balance = float(computed_after)
    session.add(user)

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="CREDIT_REFUND",
        entity_id=str(lot.id),
        before_json={
            "cached_balance": float(cached_before),
            "computed_balance": float(computed_before),
        },
        after_json={
            "credit_lot_id": lot.id,
            "ledger_id": ledger.id,
            "computed_balance": float(computed_after),
        },
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    summary = _build_wallet_summary(session, user)
    return RefundResponse(
        id=lot.id,
        user_id=lot.user_id,
        user_email=user.email,
        credits=float(lot.credits_total),
        reason_code=lot.reason_code,
        source_attempt_id=lot.source_attempt_id,
        source_payment_id=lot.source_payment_id,
        expires_at=lot.expires_at,
        created_at=lot.purchased_at,
        ledger_id=ledger.id,
        wallet_summary=summary.dict(),
    )
