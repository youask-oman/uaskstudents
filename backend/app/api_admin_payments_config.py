from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select, desc, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.database import get_session
from app.models import (
    User, ProviderModelPricing, ProviderPricingAuditEvent, 
    ProviderPricingAction, SystemConfigVersion, SystemConfig
)
from app.api_admin import get_staff_user, get_admin_user
from app.services.admin_config_service import admin_config_service

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments-config"])

# --- Payment Strategy Config (SystemConfig) ---

PAYMENTS_CONFIG_TYPE = "payments_config"

@router.get("/config")
def get_payments_config(
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get global payment system configuration."""
    config = admin_config_service.get_active_config(session, PAYMENTS_CONFIG_TYPE)
    # Default values if not set
    defaults = {
        "credit_value_usd": 0.10,
        "multipliers": {
            "STANDARD": 1.0,
            "RESEARCH": 2.0
        },
        "fixed_fees": {
            "ocr": 1.0,
            "voice": 1.0
        },
        "minimum_charge_credits": 1,
        "topup_expiry_days": 365,
        "subscription_grant_policy": "PRORATED_MONTHLY",
        "tax_defaults": {
            "mode": "NONE",
            "rate": 0.0
        },
        "invoice_settings": {
            "footer_text": "Thank you for using uask.ai",
            "company_name": "uask.ai",
            "company_address": "123 AI Lane, Tech City"
        },
        "stripe_mappings": {} # TopUpProduct.code -> price_id, Plan.code -> price_id
    }
    # Merge defaults
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
        elif isinstance(v, dict) and isinstance(config[k], dict):
            for sk, sv in v.items():
                if sk not in config[k]:
                    config[k][sk] = sv

    return {
        "config": config,
        "history": admin_config_service.get_history(session, PAYMENTS_CONFIG_TYPE, limit=10)
    }

@router.put("/config")
def update_payments_config(
    payload: Dict[str, Any] = Body(...),
    reason: str = Body(..., embed=True),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Update global payment system configuration with audit trail."""
    # Strip history or metadata if accidentally passed
    if "config" in payload:
        new_config = payload["config"]
    else:
        new_config = payload

    version = admin_config_service.update_config(
        session=session,
        config_type=PAYMENTS_CONFIG_TYPE,
        new_value=new_config,
        user_id=user.id,
        change_msg=reason
    )
    return {"status": "ok", "version": version.version}


# --- Provider Model Pricing (CRUD) ---

@router.get("/pricing")
def list_provider_pricing(
    provider: Optional[str] = "openai",
    model: Optional[str] = None,
    show_inactive_gpt5: bool = Query(False, description="Show inactive GPT-5 family models"),
    all_history: bool = Query(False, description="Show all historical versions"),
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """
    List pricing entries for provider/model.
    
    By default:
    - Shows only OpenAI pricing
    - Shows only gpt-5-mini (active)
    - Set show_inactive_gpt5=true to also see gpt-5 and gpt-5-nano
    """
    # HARD RULE: Only OpenAI is supported
    if provider and provider.lower() != "openai":
        raise HTTPException(400, detail="Only OpenAI provider is supported")
    
    query = select(ProviderModelPricing).where(
        ProviderModelPricing.provider == "openai"
    )
    
    # Model filtering
    if model:
        # Specific model requested
        if not model.startswith("gpt-5"):
            raise HTTPException(400, detail="Only GPT-5 family models are supported")
        query = query.where(ProviderModelPricing.model == model)
    else:
        # Default: show gpt-5-mini only, unless advanced toggle is on
        if show_inactive_gpt5:
            # Show all GPT-5 family
            query = query.where(ProviderModelPricing.model.like("gpt-5%"))
        else:
            # Show only gpt-5-mini
            query = query.where(ProviderModelPricing.model == "gpt-5-mini")
    
    # Status filtering
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
            "all_history": all_history
        }
    }

@router.post("/pricing")
def create_provider_pricing(
    pricing: ProviderModelPricing,
    reason: str = Body(..., embed=True),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """
    Create a new pricing entry. 
    Enforces no-overlap by retiring previous active entry.
    """
    # HARD RULE: Only OpenAI GPT-5 family
    if pricing.provider.lower() != "openai":
        raise HTTPException(400, detail="Only OpenAI provider is supported")
    
    if not pricing.model.startswith("gpt-5"):
        raise HTTPException(400, detail="Only GPT-5 family models are supported")
    
    # Check if advanced models are allowed for non-mini models
    if pricing.model != "gpt-5-mini":
        allow_advanced = session.exec(
            select(SystemConfig).where(SystemConfig.key == "ALLOW_ADVANCED_MODELS")
        ).first()
        
        if not allow_advanced or allow_advanced.value != "true":
            raise HTTPException(
                403, 
                detail=f"Advanced model {pricing.model} is not enabled. Only gpt-5-mini is currently allowed."
            )

    # Find current active pricing
    statement = select(ProviderModelPricing).where(
        and_(
            ProviderModelPricing.provider == pricing.provider,
            ProviderModelPricing.model == pricing.model,
            ProviderModelPricing.status == "ACTIVE"
        )
    )
    current_active = session.exec(statement).first()

    now = datetime.utcnow()
    # If effective_from is not set or in the past, set to now
    if not pricing.effective_from or pricing.effective_from < now:
        pricing.effective_from = now

    # Retire previous active if it overlaps
    if current_active:
        if current_active.effective_from >= pricing.effective_from:
            # Cannot create pricing starting before current active's start
            raise HTTPException(400, detail="New pricing must start after current active pricing start date")
        
        current_active.effective_to = pricing.effective_from
        current_active.status = "INACTIVE"
        session.add(current_active)
        
        # Log retirement
        audit_retire = ProviderPricingAuditEvent(
            admin_user_id=user.id,
            provider_model_pricing_id=current_active.id,
            action=ProviderPricingAction.RETIRE,
            before_json=current_active.dict(),
            after_json=current_active.dict(), # status changed
            reason=f"Retired to make room for new pricing: {reason}"
        )
        session.add(audit_retire)

    # Save new pricing
    pricing.id = None
    pricing.status = "ACTIVE"
    pricing.created_by = user.id
    pricing.change_reason = reason
    session.add(pricing)
    session.flush()

    # Log creation
    audit_create = ProviderPricingAuditEvent(
        admin_user_id=user.id,
        provider_model_pricing_id=pricing.id,
        action=ProviderPricingAction.CREATE,
        after_json=pricing.dict(),
        reason=reason
    )
    session.add(audit_create)
    session.commit()
    session.refresh(pricing)
    return pricing

@router.put("/pricing/{pricing_id}")
def update_provider_pricing(
    pricing_id: int,
    updates: Dict[str, Any] = Body(...),
    reason: str = Body(..., embed=True),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """
    Update future-dated pricing rows. Past rows cannot be edited.
    """
    pricing = session.get(ProviderModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(404, detail="Pricing row not found")
    
    now = datetime.utcnow()
    if pricing.effective_from <= now:
        raise HTTPException(400, detail="Cannot edit active or past pricing rows. Create a new version instead.")

    before = pricing.dict()
    # Apply updates (selective)
    for k, v in updates.items():
        if hasattr(pricing, k) and k not in ["id", "created_at", "created_by"]:
            setattr(pricing, k, v)
    
    pricing.change_reason = reason
    session.add(pricing)
    
    # Audit log
    audit = ProviderPricingAuditEvent(
        admin_user_id=user.id,
        provider_model_pricing_id=pricing.id,
        action=ProviderPricingAction.UPDATE,
        before_json=before,
        after_json=pricing.dict(),
        reason=reason
    )
    session.add(audit)
    session.commit()
    return pricing

@router.delete("/pricing/{pricing_id}")
def retire_provider_pricing(
    pricing_id: int,
    reason: str = Body(..., embed=True),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Retire (soft delete) a pricing entry."""
    pricing = session.get(ProviderModelPricing, pricing_id)
    if not pricing:
        raise HTTPException(404, detail="Pricing row not found")
    
    if pricing.status == "INACTIVE":
        return {"status": "already inactive"}

    before = pricing.dict()
    pricing.status = "INACTIVE"
    pricing.effective_to = datetime.utcnow()
    pricing.change_reason = reason
    session.add(pricing)
    
    audit = ProviderPricingAuditEvent(
        admin_user_id=user.id,
        provider_model_pricing_id=pricing.id,
        action=ProviderPricingAction.RETIRE,
        before_json=before,
        after_json=pricing.dict(),
        reason=reason
    )
    session.add(audit)
    session.commit()
    return {"status": "ok"}
