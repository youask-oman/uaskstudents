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
        request=request,
    )
    
    session.commit()
    
    return {"success": True, "hold_id": hold_id, "new_status": hold.status}


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
