"""
Admin Billing: Holds & Settlement API

Endpoints for viewing and managing credit holds.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, CreditHold
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service
from app.admin_billing.billing_wallet import _build_wallet_summary
from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
from app.services.billing_exceptions import HoldAlreadyFinalizedError, HoldNotFoundError

router = APIRouter(prefix="/api/admin/billing/holds", tags=["admin-billing-holds"])


class HoldResponse(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    subscription_id: int
    request_id: str
    reserved_credits: float
    status: str
    meta: Optional[dict]
    created_at: datetime
    finalized_at: Optional[datetime]
    age_seconds: int

    class Config:
        from_attributes = True


class ReleaseHoldRequest(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None


class ReleaseOcrHoldsRequest(BaseModel):
    reason: str
    user_id: Optional[int] = None
    min_age_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedResponse)
async def list_holds(
    status: Optional[str] = "held",
    user_id: Optional[int] = None,
    min_age_seconds: Optional[int] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List credit holds with filters."""
    query = select(CreditHold)
    count_query = select(func.count(CreditHold.id))
    
    if status:
        query = query.where(CreditHold.status == status)
        count_query = count_query.where(CreditHold.status == status)
    
    if user_id:
        query = query.where(CreditHold.user_id == user_id)
        count_query = count_query.where(CreditHold.user_id == user_id)
    
    total = session.exec(count_query).one()
    holds = session.exec(
        query.order_by(CreditHold.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    now = datetime.utcnow()
    
    # Get user emails
    user_ids = {h.user_id for h in holds}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all()}
    
    results = []
    for h in holds:
        age = int((now - h.created_at).total_seconds())
        
        # Filter by min age if specified
        if min_age_seconds and age < min_age_seconds:
            continue
        
        user = users.get(h.user_id)
        results.append(HoldResponse(
            id=h.id,
            user_id=h.user_id,
            user_email=user.email if user else None,
            subscription_id=h.subscription_id,
            request_id=h.request_id,
            reserved_credits=float(h.reserved_credits) if h.reserved_credits else 0,
            status=h.status,
            meta=h.meta if hasattr(h, 'meta') else None,
            created_at=h.created_at,
            finalized_at=h.finalized_at,
            age_seconds=age,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.post("/{hold_id}/release")
async def force_release_hold(
    hold_id: int,
    body: ReleaseHoldRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Force release a hold. Requires superadmin."""
    hold = session.get(CreditHold, hold_id)
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    
    if hold.status != "held":
        raise HTTPException(status_code=400, detail=f"Hold already finalized with status: {hold.status}")
    
    before = {"status": hold.status, "reserved_credits": float(hold.reserved_credits)}
    
    hold.status = "released_admin"
    hold.finalized_at = datetime.utcnow()
    session.add(hold)
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="CREDIT_HOLD",
        entity_id=str(hold_id),
        before_json=before,
        after_json={"status": hold.status},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()

    user = session.get(User, hold.user_id)
    summary = _build_wallet_summary(session, user) if user else None
    return {
        "success": True,
        "hold_id": hold_id,
        "new_status": hold.status,
        "wallet_summary": summary.dict() if summary else None,
    }


@router.post("/release-ocr")
async def release_ocr_holds(
    body: ReleaseOcrHoldsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Release all OCR holds (request_id starts with 'ocr:')."""
    query = select(CreditHold).where(CreditHold.status == "held").where(CreditHold.request_id.like("ocr:%"))
    if body.user_id:
        query = query.where(CreditHold.user_id == body.user_id)
    holds = session.exec(query.order_by(CreditHold.created_at.desc())).all()
    now = datetime.utcnow()

    released = 0
    skipped = 0
    for hold in holds:
        if body.min_age_seconds:
            age = int((now - hold.created_at).total_seconds())
            if age < body.min_age_seconds:
                skipped += 1
                continue
        try:
            billing_ledger_service_v2.release_hold(
                session=session,
                request_id=hold.request_id,
                attempt_id=str(hold.id),
            )
            released += 1
        except (HoldAlreadyFinalizedError, HoldNotFoundError):
            skipped += 1

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="OCR_HOLD_RELEASE",
        entity_id=str(body.user_id) if body.user_id else "all",
        before_json={"holds_found": len(holds)},
        after_json={"released": released, "skipped": skipped},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    return {
        "success": True,
        "released": released,
        "skipped": skipped,
        "total_found": len(holds),
    }


@router.get("/stats")
async def get_hold_stats(
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get hold statistics."""
    now = datetime.utcnow()
    
    # Active holds
    active_count = session.exec(
        select(func.count(CreditHold.id)).where(CreditHold.status == "held")
    ).one()
    
    # Stuck holds (> 1 hour)
    stuck_holds = session.exec(
        select(CreditHold).where(CreditHold.status == "held")
    ).all()
    
    stuck_count = 0
    max_age = 0
    total_reserved = 0
    
    for h in stuck_holds:
        age = int((now - h.created_at).total_seconds())
        total_reserved += float(h.reserved_credits) if h.reserved_credits else 0
        if age > 3600:  # > 1 hour
            stuck_count += 1
        max_age = max(max_age, age)
    
    return {
        "active_holds": active_count,
        "stuck_holds_1hr": stuck_count,
        "max_age_seconds": max_age,
        "total_reserved_credits": total_reserved,
    }
