from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlmodel import Session, select, desc, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.database import get_session
from app.models import (
    User,
    ProviderModelPricing,
    ProviderPricingAuditEvent,
    ProviderPricingAction,
    SystemConfigVersion,
    SystemConfig,
    TopUpProduct,
    StripePriceMap,
)
from app.models.admin_audit_log import AdminAuditLog
from app.api_admin import get_staff_user, get_admin_user
from app.admin_billing.deps import get_superadmin_user
from app.services.audit_log_service import audit_log_service
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
def list_payments_pricing(
    provider: Optional[str] = "openai",
    model: Optional[str] = None,
    show_inactive_gpt5: bool = Query(False, description="Show inactive GPT-5 family models"),
    all_history: bool = Query(False, description="Show all historical versions"),
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user),
):
    """
    Combined pricing view: provider pricing + credit packs + Stripe price map.
    """
    provider_pricing = list_provider_pricing(
        provider=provider,
        model=model,
        show_inactive_gpt5=show_inactive_gpt5,
        all_history=all_history,
        session=session,
        user=user,
    )

    packs = session.exec(select(TopUpProduct).order_by(TopUpProduct.id.desc())).all()
    price_map = session.exec(select(StripePriceMap).order_by(StripePriceMap.id.desc())).all()

    return {
        "provider_pricing": provider_pricing,
        "topup_packs": packs,
        "stripe_price_map": price_map,
    }


@router.post("/pricing")
def mutate_payments_pricing(
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_superadmin_user),
):
    """
    Mutate top-up packs or Stripe price mappings (superadmin only).
    Payload shape:
      { kind: "TOPUP_PACK"|"STRIPE_PRICE_MAP", action: "create"|"update"|"deactivate", data: {...}, reason: "..." }
    """
    kind = payload.get("kind")
    action = payload.get("action")
    data = payload.get("data") or {}
    reason = payload.get("reason") or ""
    idempotency_key = payload.get("idempotency_key")
    if not reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    if idempotency_key:
        existing = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.idempotency_key == idempotency_key)
        ).first()
        if existing:
            return {"status": "idempotent_replay", "audit_id": existing.id}

    if kind == "TOPUP_PACK":
        pack_id = data.get("id")
        if action == "create":
            pack = TopUpProduct(
                code=data.get("code"),
                name=data.get("name"),
                credits=int(data.get("credits")),
                price_usd=float(data.get("price_usd")),
                is_active=bool(data.get("is_active", True)),
                metadata_json=data.get("metadata_json"),
            )
            session.add(pack)
            session.flush()
            audit_log_service.log_action(
                session=session,
                admin_user_id=user.id,
                action="CREATE",
                entity_type="TOPUP_PRODUCT",
                entity_id=str(pack.id),
                before_json={"status": "new"},
                after_json={"code": pack.code, "credits": pack.credits, "price_usd": pack.price_usd},
                reason=reason,
                idempotency_key=idempotency_key,
                request=request,
            )
            session.commit()
            session.refresh(pack)
            return pack
        if action in {"update", "deactivate"}:
            if not pack_id:
                raise HTTPException(status_code=400, detail="id required for update/deactivate")
            pack = session.get(TopUpProduct, int(pack_id))
            if not pack:
                raise HTTPException(status_code=404, detail="Pack not found")
            before = {"code": pack.code, "credits": pack.credits, "price_usd": pack.price_usd, "is_active": pack.is_active}
            if action == "deactivate":
                pack.is_active = False
            else:
                for field in ["name", "credits", "price_usd", "is_active", "metadata_json"]:
                    if field in data:
                        setattr(pack, field, data[field])
            session.add(pack)
            audit_log_service.log_action(
                session=session,
                admin_user_id=user.id,
                action="UPDATE" if action == "update" else "DELETE",
                entity_type="TOPUP_PRODUCT",
                entity_id=str(pack.id),
                before_json=before,
                after_json={"code": pack.code, "credits": pack.credits, "price_usd": pack.price_usd, "is_active": pack.is_active},
                reason=reason,
                idempotency_key=idempotency_key,
                request=request,
            )
            session.commit()
            session.refresh(pack)
            return pack
        raise HTTPException(status_code=400, detail="Unsupported action for TOPUP_PACK")

    if kind == "STRIPE_PRICE_MAP":
        mapping_id = data.get("id")
        if action == "create":
            mapping = StripePriceMap(
                kind=data.get("kind"),
                internal_code=data.get("internal_code"),
                stripe_price_id=data.get("stripe_price_id"),
                currency=data.get("currency") or "USD",
                active=bool(data.get("active", True)),
            )
            session.add(mapping)
            session.flush()
            audit_log_service.log_action(
                session=session,
                admin_user_id=user.id,
                action="CREATE",
                entity_type="STRIPE_PRICE_MAP",
                entity_id=str(mapping.id),
                before_json={"status": "new"},
                after_json={"kind": mapping.kind, "internal_code": mapping.internal_code, "stripe_price_id": mapping.stripe_price_id},
                reason=reason,
                idempotency_key=idempotency_key,
                request=request,
            )
            session.commit()
            session.refresh(mapping)
            return mapping
        if action in {"update", "deactivate"}:
            if not mapping_id:
                raise HTTPException(status_code=400, detail="id required for update/deactivate")
            mapping = session.get(StripePriceMap, int(mapping_id))
            if not mapping:
                raise HTTPException(status_code=404, detail="Mapping not found")
            before = {"kind": mapping.kind, "internal_code": mapping.internal_code, "stripe_price_id": mapping.stripe_price_id, "active": mapping.active}
            if action == "deactivate":
                mapping.active = False
            else:
                for field in ["kind", "internal_code", "stripe_price_id", "currency", "active"]:
                    if field in data:
                        setattr(mapping, field, data[field])
            session.add(mapping)
            audit_log_service.log_action(
                session=session,
                admin_user_id=user.id,
                action="UPDATE" if action == "update" else "DELETE",
                entity_type="STRIPE_PRICE_MAP",
                entity_id=str(mapping.id),
                before_json=before,
                after_json={"kind": mapping.kind, "internal_code": mapping.internal_code, "stripe_price_id": mapping.stripe_price_id, "active": mapping.active},
                reason=reason,
                idempotency_key=idempotency_key,
                request=request,
            )
            session.commit()
            session.refresh(mapping)
            return mapping
        raise HTTPException(status_code=400, detail="Unsupported action for STRIPE_PRICE_MAP")

    raise HTTPException(status_code=400, detail="Unsupported pricing kind")


@router.get("/pricing/provider")
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
            "all_history": all_history,
        },
    }

@router.post("/pricing/provider")
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

@router.put("/pricing/provider/{pricing_id}")
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

@router.delete("/pricing/provider/{pricing_id}")
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
