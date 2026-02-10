"""
Admin Billing: Pricing API

Provides an alias for provider pricing management under /api/admin/billing/pricing.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlmodel import Session, select, desc, and_

from app.database import get_session
from app.models import ProviderModelPricing, SystemConfig, User
from app.api_admin import get_staff_user, get_admin_user

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

    if pricing_data.provider.lower() != "openai":
        raise HTTPException(400, detail="Only OpenAI provider is supported")
    if not pricing_data.model.startswith("gpt-5"):
        raise HTTPException(400, detail="Only GPT-5 family models are supported")

    if pricing_data.model != "gpt-5-mini":
        allow_advanced = session.exec(
            select(SystemConfig).where(SystemConfig.key == "ALLOW_ADVANCED_MODELS")
        ).first()
        if not allow_advanced or allow_advanced.value != "true":
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

    if current_active:
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
    session.commit()
    session.refresh(pricing)

    return pricing
