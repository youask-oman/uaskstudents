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
from app.models import User, CreditLot
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service

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
    
    # Idempotency check
    if body.idempotency_key:
        existing = session.exec(
            select(CreditLot)
            .where(CreditLot.lot_type == "REFUND")
            .where(CreditLot.user_id == body.user_id)
            .where(CreditLot.reason_code == body.idempotency_key)
        ).first()
        if existing:
            return RefundResponse(
                id=existing.id,
                user_id=existing.user_id,
                user_email=user.email,
                credits=float(existing.credits_total) if existing.credits_total else 0,
                reason_code=existing.reason_code,
                source_attempt_id=existing.source_attempt_id,
                source_payment_id=existing.source_payment_id,
                expires_at=existing.expires_at,
                created_at=existing.purchased_at,
            )
    
    # Create refund lot
    lot = CreditLot(
        user_id=body.user_id,
        lot_type="REFUND",
        credits_total=Decimal(str(body.credits)),
        credits_remaining=Decimal(str(body.credits)),
        status="ACTIVE",
        reason_code=body.reason_code,
        source_attempt_id=body.source_attempt_id,
        source_payment_id=body.source_payment_id,
        purchased_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=body.expires_days),
    )
    session.add(lot)
    session.flush()
    
    # Update cached balance
    user.credits_balance = float(Decimal(str(user.credits_balance or 0)) + Decimal(str(body.credits)))
    session.add(user)
    
    # Audit log
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="REFUND",
        entity_id=str(lot.id),
        after_json={
            "user_id": body.user_id,
            "credits": body.credits,
            "reason_code": body.reason_code,
        },
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    
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
    )
