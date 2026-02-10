"""
Admin Billing: Credit Packs (TopUp Products) API

CRUD for top-up products stored in TopUpProduct.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import TopUpProduct, User
from app.models.admin_audit_log import AdminAuditLog
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service

router = APIRouter(prefix="/api/admin/billing/packs", tags=["admin-billing-packs"])


class PackResponse(BaseModel):
    id: int
    code: str
    name: str
    credits: int
    price_usd: float
    is_active: bool
    description: Optional[str] = None
    metadata_json: Optional[dict] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List[PackResponse]
    total: int
    limit: int
    offset: int


class PackCreateRequest(BaseModel):
    code: str
    name: str
    credits: int
    price_usd: float
    is_active: bool = True
    description: Optional[str] = None
    reason: str
    idempotency_key: Optional[str] = None


class PackUpdateRequest(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    price_usd: Optional[float] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    reason: str
    idempotency_key: Optional[str] = None


class PackDeactivateRequest(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None


def _require_reason(reason: str):
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")


def _pack_description(metadata: Optional[dict]) -> Optional[str]:
    if not metadata:
        return None
    desc = metadata.get("description")
    return desc if isinstance(desc, str) and desc.strip() else None


def _pack_to_response(pack: TopUpProduct) -> PackResponse:
    return PackResponse(
        id=pack.id,
        code=pack.code,
        name=pack.name,
        credits=pack.credits,
        price_usd=pack.price_usd,
        is_active=pack.is_active,
        description=_pack_description(pack.metadata_json),
        metadata_json=pack.metadata_json,
    )


def _audit_idempotent_lookup(
    session: Session,
    idempotency_key: Optional[str],
) -> Optional[AdminAuditLog]:
    if not idempotency_key:
        return None
    return session.exec(
        select(AdminAuditLog)
        .where(AdminAuditLog.idempotency_key == idempotency_key)
        .where(AdminAuditLog.entity_type == "TOPUP_PRODUCT")
        .order_by(AdminAuditLog.created_at.desc())
    ).first()


@router.get("", response_model=PaginatedResponse)
def list_packs(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    query = select(TopUpProduct)
    count_query = select(func.count(TopUpProduct.id))

    if status and status.lower() != "all":
        is_active = status.lower() == "active"
        query = query.where(TopUpProduct.is_active == is_active)
        count_query = count_query.where(TopUpProduct.is_active == is_active)

    total = session.exec(count_query).one()
    packs = session.exec(
        query.order_by(TopUpProduct.id.desc()).offset(offset).limit(limit)
    ).all()

    return PaginatedResponse(
        items=[_pack_to_response(pack) for pack in packs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PackResponse)
def create_pack(
    body: PackCreateRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    _require_reason(body.reason)

    existing_audit = _audit_idempotent_lookup(session, body.idempotency_key)
    if existing_audit and existing_audit.entity_id:
        existing_pack = session.get(TopUpProduct, int(existing_audit.entity_id))
        if existing_pack:
            return _pack_to_response(existing_pack)

    existing = session.exec(select(TopUpProduct).where(TopUpProduct.code == body.code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Pack code already exists")

    metadata = {}
    if body.description and body.description.strip():
        metadata["description"] = body.description.strip()

    pack = TopUpProduct(
        code=body.code.strip(),
        name=body.name.strip(),
        credits=int(body.credits),
        price_usd=float(body.price_usd),
        is_active=bool(body.is_active),
        metadata_json=metadata or None,
    )
    session.add(pack)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="TOPUP_PRODUCT",
        entity_id=str(pack.id),
        before_json={"status": "new"},
        after_json={
            "code": pack.code,
            "name": pack.name,
            "credits": pack.credits,
            "price_usd": pack.price_usd,
            "is_active": pack.is_active,
        },
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()
    session.refresh(pack)
    return _pack_to_response(pack)


@router.put("/{pack_id}", response_model=PackResponse)
def update_pack(
    pack_id: int,
    body: PackUpdateRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    _require_reason(body.reason)

    existing_audit = _audit_idempotent_lookup(session, body.idempotency_key)
    if existing_audit and existing_audit.entity_id:
        existing_pack = session.get(TopUpProduct, int(existing_audit.entity_id))
        if existing_pack:
            return _pack_to_response(existing_pack)

    pack = session.get(TopUpProduct, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    before = _pack_to_response(pack).dict()

    if body.name is not None:
        pack.name = body.name.strip()
    if body.credits is not None:
        pack.credits = int(body.credits)
    if body.price_usd is not None:
        pack.price_usd = float(body.price_usd)
    if body.is_active is not None:
        pack.is_active = bool(body.is_active)

    metadata = dict(pack.metadata_json or {})
    if body.description is not None:
        desc = body.description.strip()
        if desc:
            metadata["description"] = desc
        else:
            metadata.pop("description", None)
    pack.metadata_json = metadata or None

    session.add(pack)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="UPDATE",
        entity_type="TOPUP_PRODUCT",
        entity_id=str(pack.id),
        before_json=before,
        after_json=_pack_to_response(pack).dict(),
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()
    session.refresh(pack)
    return _pack_to_response(pack)


@router.delete("/{pack_id}", response_model=PackResponse)
def deactivate_pack(
    pack_id: int,
    body: PackDeactivateRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    _require_reason(body.reason)

    existing_audit = _audit_idempotent_lookup(session, body.idempotency_key)
    if existing_audit and existing_audit.entity_id:
        existing_pack = session.get(TopUpProduct, int(existing_audit.entity_id))
        if existing_pack:
            return _pack_to_response(existing_pack)

    pack = session.get(TopUpProduct, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    before = _pack_to_response(pack).dict()
    pack.is_active = False
    session.add(pack)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="DELETE",
        entity_type="TOPUP_PRODUCT",
        entity_id=str(pack.id),
        before_json=before,
        after_json=_pack_to_response(pack).dict(),
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()
    session.refresh(pack)
    return _pack_to_response(pack)
