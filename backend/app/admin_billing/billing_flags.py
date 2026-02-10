"""
Admin Billing: Feature Flags API

Endpoints for viewing and managing billing feature flags.
Requires superadmin for mutations.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.models.admin_audit_log import AdminAuditLog
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.billing_feature_flags import get_feature_flags
from app.services.audit_log_service import audit_log_service

router = APIRouter(prefix="/api/admin/billing", tags=["admin-billing-flags"])
legacy_router = APIRouter(prefix="/admin/billing", tags=["admin-billing-flags-legacy"])


# Request/Response Models
class FeatureFlagsResponse(BaseModel):
    billing_v2_enabled: bool
    billing_v2_rollout_percent: int
    credit_programs_enabled: bool
    refund_v2_enabled: bool
    reconciliation_autofix_enabled: bool
    admin_ids: List[int]


class UpdateFlagsRequest(BaseModel):
    billing_v2_enabled: Optional[bool] = None
    billing_v2_rollout_percent: Optional[int] = None
    credit_programs_enabled: Optional[bool] = None
    refund_v2_enabled: Optional[bool] = None
    reconciliation_autofix_enabled: Optional[bool] = None
    reason: str  # Required for audit


class FlagAuditEntry(BaseModel):
    id: int
    admin_user_id: int
    admin_email: Optional[str] = None
    flag_name: str
    old_value: str
    new_value: str
    reason: Optional[str]
    created_at: datetime


@router.get("/flags", response_model=FeatureFlagsResponse)
@legacy_router.get("/flags", response_model=FeatureFlagsResponse)
async def get_flags(
    admin: User = Depends(get_admin_user),
):
    """Get current feature flag states."""
    flags = get_feature_flags()
    return FeatureFlagsResponse(
        billing_v2_enabled=flags._billing_v2,
        billing_v2_rollout_percent=flags._v2_rollout_percent,
        credit_programs_enabled=flags._credit_programs,
        refund_v2_enabled=flags._refund_v2,
        reconciliation_autofix_enabled=flags._reconciliation_autofix,
        admin_ids=list(flags._admin_ids),
    )


@router.put("/flags", response_model=FeatureFlagsResponse)
@legacy_router.put("/flags", response_model=FeatureFlagsResponse)
async def update_flags(
    request_body: UpdateFlagsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """
    Update feature flags. Requires superadmin.
    
    Changes take effect immediately (no redeploy required).
    All changes are audited.
    """
    flags = get_feature_flags()
    
    # Track changes for audit
    changes = []
    
    if request_body.billing_v2_enabled is not None:
        old_val = flags._billing_v2
        flags._billing_v2 = request_body.billing_v2_enabled
        if old_val != request_body.billing_v2_enabled:
            changes.append(("billing_v2_enabled", old_val, request_body.billing_v2_enabled))
    
    if request_body.billing_v2_rollout_percent is not None:
        old_val = flags._v2_rollout_percent
        flags._v2_rollout_percent = request_body.billing_v2_rollout_percent
        if old_val != request_body.billing_v2_rollout_percent:
            changes.append(("billing_v2_rollout_percent", old_val, request_body.billing_v2_rollout_percent))
    
    if request_body.credit_programs_enabled is not None:
        old_val = flags._credit_programs
        flags._credit_programs = request_body.credit_programs_enabled
        if old_val != request_body.credit_programs_enabled:
            changes.append(("credit_programs_enabled", old_val, request_body.credit_programs_enabled))
    
    if request_body.refund_v2_enabled is not None:
        old_val = flags._refund_v2
        flags._refund_v2 = request_body.refund_v2_enabled
        if old_val != request_body.refund_v2_enabled:
            changes.append(("refund_v2_enabled", old_val, request_body.refund_v2_enabled))
    
    if request_body.reconciliation_autofix_enabled is not None:
        old_val = flags._reconciliation_autofix
        flags._reconciliation_autofix = request_body.reconciliation_autofix_enabled
        if old_val != request_body.reconciliation_autofix_enabled:
            changes.append(("reconciliation_autofix_enabled", old_val, request_body.reconciliation_autofix_enabled))
    
    # Create audit entries for each change
    for flag_name, old_val, new_val in changes:
        audit_log_service.log_flag_change(
            session=session,
            admin_user_id=admin.id,
            flag_name=flag_name,
            old_value=old_val,
            new_value=new_val,
            reason=request_body.reason,
            request=request,
        )
    
    session.commit()
    
    return FeatureFlagsResponse(
        billing_v2_enabled=flags._billing_v2,
        billing_v2_rollout_percent=flags._v2_rollout_percent,
        credit_programs_enabled=flags._credit_programs,
        refund_v2_enabled=flags._refund_v2,
        reconciliation_autofix_enabled=flags._reconciliation_autofix,
        admin_ids=list(flags._admin_ids),
    )


@router.get("/flags/audit", response_model=List[FlagAuditEntry])
@legacy_router.get("/flags/audit", response_model=List[FlagAuditEntry])
async def get_flags_audit(
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get audit log of feature flag changes."""
    entries = session.exec(
        select(AdminAuditLog)
        .where(AdminAuditLog.entity_type == "FEATURE_FLAG")
        .order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    # Get admin emails
    admin_ids = {e.admin_user_id for e in entries}
    admins = {u.id: u for u in session.exec(select(User).where(User.id.in_(admin_ids))).all()}
    
    results = []
    for entry in entries:
        admin_user = admins.get(entry.admin_user_id)
        results.append(FlagAuditEntry(
            id=entry.id,
            admin_user_id=entry.admin_user_id,
            admin_email=admin_user.email if admin_user else None,
            flag_name=entry.entity_id or "",
            old_value=str(entry.before_json.get("value", "")) if entry.before_json else "",
            new_value=str(entry.after_json.get("value", "")) if entry.after_json else "",
            reason=entry.reason,
            created_at=entry.created_at,
        ))
    
    return results
