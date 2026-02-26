"""
Admin Billing: Pricing API

Provides an alias for provider pricing management under /api/admin/billing/pricing.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlmodel import Session, select, desc, and_

from app.database import get_session
from app.models import ProviderModelPricing, User
from app.models.admin_audit_log import AdminAuditLog
from app.api_admin import get_staff_user, get_admin_user
from app.services.audit_log_service import audit_log_service

router = APIRouter(prefix="/api/admin/billing/pricing", tags=["admin-billing-pricing"])


class PricingPayload(BaseModel):
    provider: str = "openai"
    model: str = "gpt-5-mini"
    price_in_per_1m: float
    price_out_per_1m: float
    price_cached_in_per_1m: float = 0.0
    currency: str = "USD"
    effective_from: Optional[datetime] = None


class PricingCreateRequest(BaseModel):
    pricing: PricingPayload
    reason: str
    idempotency_key: Optional[str] = None


class PricingDeactivateRequest(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None


@router.get("")
def list_provider_pricing(
    provider: Optional[str] = "openai",
    model: Optional[str] = None,
    show_inactive_gpt5: bool = Query(False),
    all_history: bool = Query(False),
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    if provider and provider.lower() != "openai":
        raise HTTPException(400, detail="Only OpenAI provider is supported")

    query = select(ProviderModelPricing).where(
        ProviderModelPricing.provider == "openai"
    )

    if model:
        if not model.startswith("gpt-5"):
            raise HTTPException(400, detail="Only GPT-5 family models are supported")
        query = query.where(ProviderModelPricing.model == model)
    else:
        if show_inactive_gpt5:
            query = query.where(ProviderModelPricing.model.like("gpt-5%"))
        else:
            query = query.where(ProviderModelPricing.model == "gpt-5-mini")

    if not all_history:
        query = query.where(ProviderModelPricing.status == "ACTIVE")

    query = query.order_by(desc(ProviderModelPricing.effective_from))
    results = session.exec(query).all()

    return {
        "pricing": results,
        "filters": {
            "provider": "openai",
            "model": model or ("gpt-5*" if show_inactive_gpt5 else "gpt-5-mini"),
            "show_inactive_gpt5": show_inactive_gpt5,
            "all_history": all_history,
        },
    }


@router.post("")
def create_provider_pricing(
    payload: PricingCreateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    pricing_data = payload.pricing
    reason = payload.reason
    idempotency_key = payload.idempotency_key

    if idempotency_key:
        existing_audit = session.exec(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "PRICING")
            .where(AdminAuditLog.idempotency_key == idempotency_key)
            .order_by(AdminAuditLog.created_at.desc())
        ).first()
        if existing_audit and existing_audit.entity_id:
            existing = session.get(ProviderModelPricing, int(existing_audit.entity_id))
            if existing:
                return existing

    if pricing_data.provider.lower() != "openai":
        raise HTTPException(400, detail="Only OpenAI provider is supported")
    if not pricing_data.model.startswith("gpt-5"):
        raise HTTPException(400, detail="Only GPT-5 family models are supported")

    if pricing_data.model != "gpt-5-mini":
        allow_advanced = (os.getenv("ALLOW_ADVANCED_MODELS") or "false").strip().lower() in {"1", "true", "yes", "on"}
        if not allow_advanced:
            raise HTTPException(
                403,
                detail=f"Advanced model {pricing_data.model} is not enabled.",
            )

    statement = select(ProviderModelPricing).where(
        and_(
            ProviderModelPricing.provider == pricing_data.provider,
            ProviderModelPricing.model == pricing_data.model,
            ProviderModelPricing.status == "ACTIVE",
        )
    )
    current_active = session.exec(statement).first()

    now = datetime.utcnow()
    effective_from = pricing_data.effective_from or now
    if effective_from < now:
        effective_from = now

    before_snapshot = None
    if current_active:
        before_snapshot = {
            "id": current_active.id,
            "provider": current_active.provider,
            "model": current_active.model,
            "price_in_per_1m": current_active.price_in_per_1m,
            "price_out_per_1m": current_active.price_out_per_1m,
            "price_cached_in_per_1m": current_active.price_cached_in_per_1m,
            "status": current_active.status,
            "effective_from": current_active.effective_from.isoformat(),
        }
        if current_active.effective_from >= effective_from:
            raise HTTPException(400, detail="New pricing must start after current active pricing start date")
        current_active.effective_to = effective_from
        current_active.status = "INACTIVE"
        session.add(current_active)

    pricing = ProviderModelPricing(
        provider=pricing_data.provider,
        model=pricing_data.model,
        price_in_per_1m=pricing_data.price_in_per_1m,
        price_out_per_1m=pricing_data.price_out_per_1m,
        price_cached_in_per_1m=pricing_data.price_cached_in_per_1m,
        currency=pricing_data.currency,
        effective_from=effective_from,
        status="ACTIVE",
        created_by=user.id,
        change_reason=reason,
    )
    session.add(pricing)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=user.id,
        action="CREATE",
        entity_type="PRICING",
        entity_id=str(pricing.id),
        before_json=before_snapshot,
        after_json={
            "id": pricing.id,
            "provider": pricing.provider,
            "model": pricing.model,
            "price_in_per_1m": pricing.price_in_per_1m,
            "price_out_per_1m": pricing.price_out_per_1m,
            "price_cached_in_per_1m": pricing.price_cached_in_per_1m,
            "status": pricing.status,
            "effective_from": pricing.effective_from.isoformat() if pricing.effective_from else None,
        },
        reason=reason,
        idempotency_key=idempotency_key,
    )

    session.commit()
    session.refresh(pricing)

    return pricing


@router.delete("/{pricing_id}")
def retire_provider_pricing(
    pricing_id: int,
    payload: PricingDeactivateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, detail="Reason is required")

    if payload.idempotency_key:
        existing_audit = session.exec(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "PRICING")
            .where(AdminAuditLog.idempotency_key == payload.idempotency_key)
            .order_by(AdminAuditLog.created_at.desc())
        ).first()
        if existing_audit and existing_audit.entity_id:
            existing = session.get(ProviderModelPricing, int(existing_audit.entity_id))
            if existing:
                return existing

    pricing = session.get(ProviderModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing entry not found")

    before = {
        "id": pricing.id,
        "provider": pricing.provider,
        "model": pricing.model,
        "status": pricing.status,
        "effective_from": pricing.effective_from.isoformat() if pricing.effective_from else None,
        "effective_to": pricing.effective_to.isoformat() if pricing.effective_to else None,
    }

    pricing.status = "INACTIVE"
    pricing.effective_to = pricing.effective_to or datetime.utcnow()
    pricing.change_reason = payload.reason
    session.add(pricing)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=user.id,
        action="DELETE",
        entity_type="PRICING",
        entity_id=str(pricing.id),
        before_json=before,
        after_json={
            "id": pricing.id,
            "status": pricing.status,
            "effective_to": pricing.effective_to.isoformat() if pricing.effective_to else None,
        },
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
    )

    session.commit()
    session.refresh(pricing)

    return pricing
