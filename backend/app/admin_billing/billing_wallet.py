"""
Admin Billing: User Wallet API

Endpoints for viewing and managing user credit wallets.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, CreditLot, CreditLotConsumption, CreditHold
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service
from app.jobs.nightly_reconciliation import compute_user_balance

router = APIRouter(prefix="/api/admin/billing/users", tags=["admin-billing-wallet"])


# Response Models
class WalletSummary(BaseModel):
    user_id: int
    user_email: str
    cached_balance: float
    computed_balance: float
    delta: float
    total_lots: int
    active_lots: int
    pending_holds: int
    pending_hold_credits: float


class CreditLotResponse(BaseModel):
    id: int
    lot_type: Optional[str]
    credits_total: float
    credits_remaining: float
    status: str
    source_program_id: Optional[int]
    source_payment_id: Optional[str]
    reason_code: Optional[str]
    purchased_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ConsumptionResponse(BaseModel):
    id: int
    credit_lot_id: int
    direction: str
    amount: float
    attempt_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GrantCreditsRequest(BaseModel):
    credits: float
    reason: str
    expires_days: int = 30
    lot_type: str = "ADJUSTMENT"


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("/{user_id}/wallet", response_model=WalletSummary)
async def get_wallet(
    user_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get wallet summary for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Compute balance from lots
    computed = compute_user_balance(session, user_id)
    cached = Decimal(str(user.credits_balance or 0))
    
    # Count lots
    total_lots = session.exec(
        select(func.count(CreditLot.id)).where(CreditLot.user_id == user_id)
    ).one()
    
    active_lots = session.exec(
        select(func.count(CreditLot.id))
        .where(CreditLot.user_id == user_id)
        .where(CreditLot.status == "ACTIVE")
        .where(CreditLot.credits_remaining > 0)
    ).one()
    
    # Pending holds
    holds = session.exec(
        select(CreditHold)
        .where(CreditHold.user_id == user_id)
        .where(CreditHold.status == "held")
    ).all()
    
    pending_hold_credits = sum(Decimal(str(h.reserved_credits)) for h in holds)
    
    return WalletSummary(
        user_id=user_id,
        user_email=user.email,
        cached_balance=float(cached),
        computed_balance=float(computed),
        delta=float(cached - computed),
        total_lots=total_lots,
        active_lots=active_lots,
        pending_holds=len(holds),
        pending_hold_credits=float(pending_hold_credits),
    )


@router.get("/{user_id}/lots", response_model=PaginatedResponse)
async def get_lots(
    user_id: int,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get credit lots for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = select(CreditLot).where(CreditLot.user_id == user_id)
    count_query = select(func.count(CreditLot.id)).where(CreditLot.user_id == user_id)
    
    if status:
        query = query.where(CreditLot.status == status)
        count_query = count_query.where(CreditLot.status == status)
    
    total = session.exec(count_query).one()
    lots = session.exec(
        query.order_by(CreditLot.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    results = [
        CreditLotResponse(
            id=lot.id,
            lot_type=lot.lot_type,
            credits_total=float(lot.credits_total) if lot.credits_total else 0,
            credits_remaining=float(lot.credits_remaining) if lot.credits_remaining else 0,
            status=lot.status,
            source_program_id=lot.source_program_id,
            source_payment_id=lot.source_payment_id,
            reason_code=lot.reason_code,
            purchased_at=lot.purchased_at,
            expires_at=lot.expires_at,
            created_at=lot.created_at,
        )
        for lot in lots
    ]
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{user_id}/consumptions", response_model=PaginatedResponse)
async def get_consumptions(
    user_id: int,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get credit consumptions for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    total = session.exec(
        select(func.count(CreditLotConsumption.id)).where(CreditLotConsumption.user_id == user_id)
    ).one()
    
    consumptions = session.exec(
        select(CreditLotConsumption)
        .where(CreditLotConsumption.user_id == user_id)
        .order_by(CreditLotConsumption.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    results = [
        ConsumptionResponse(
            id=c.id,
            credit_lot_id=c.credit_lot_id,
            direction=c.direction,
            amount=float(c.amount) if c.amount else 0,
            attempt_id=c.attempt_id,
            created_at=c.created_at,
        )
        for c in consumptions
    ]
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.post("/{user_id}/lots", response_model=CreditLotResponse)
async def grant_credits(
    user_id: int,
    body: GrantCreditsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Grant adjustment credits to a user. Requires superadmin."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    lot = CreditLot(
        user_id=user_id,
        lot_type=body.lot_type,
        credits_total=Decimal(str(body.credits)),
        credits_remaining=Decimal(str(body.credits)),
        status="ACTIVE",
        reason_code=body.reason,
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
        entity_type="CREDIT_LOT",
        entity_id=str(lot.id),
        after_json={"user_id": user_id, "credits": body.credits, "type": body.lot_type},
        reason=body.reason,
        request=request,
    )
    
    session.commit()
    
    return CreditLotResponse(
        id=lot.id,
        lot_type=lot.lot_type,
        credits_total=float(lot.credits_total),
        credits_remaining=float(lot.credits_remaining),
        status=lot.status,
        source_program_id=lot.source_program_id,
        source_payment_id=lot.source_payment_id,
        reason_code=lot.reason_code,
        purchased_at=lot.purchased_at,
        expires_at=lot.expires_at,
        created_at=lot.created_at,
    )


@router.post("/{user_id}/reconcile")
async def force_reconcile(
    user_id: int,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Force reconcile a user's balance."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    cached = Decimal(str(user.credits_balance or 0))
    computed = compute_user_balance(session, user_id)
    
    user.credits_balance = float(computed)
    session.add(user)
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="RECONCILIATION",
        entity_id=str(user_id),
        before_json={"cached_balance": float(cached)},
        after_json={"cached_balance": float(computed)},
        reason="Admin force reconcile",
        request=request,
    )
    
    session.commit()
    
    return {
        "success": True,
        "user_id": user_id,
        "old_balance": float(cached),
        "new_balance": float(computed),
        "delta": float(cached - computed),
    }
