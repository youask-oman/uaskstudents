from typing import Dict, Any, Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timezone
import logging
from decimal import Decimal

from app.database import get_session
from app.models import User, Subscription, CreditTransfer
from app.services.prompt_binding_pricing import normalize_tier_key, resolve_binding_pricing
from app.auth import SECRET_KEY, ALGORITHM
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.credit_transfer_service import credit_transfer_service, CreditTransferError
from app.services.notification_service import notification_service
# from app.auth import get_current_user # Not available in auth.py, defining locally

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Auth Helper ---
def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """Extract user from JWT token if present with proper validation."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
        
    try:
        # Decode JWT with expiration verification
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": True}  # Explicitly verify expiration
        )
        
        # Check required claims
        email = payload.get("sub")
        if not email:
            logger.warning(f"JWT token missing 'sub' claim: {payload.keys()}")
            return None
            
        # Check token issuance time (optional but recommended)
        iat = payload.get("iat")
        if iat and isinstance(iat, (int, float)):
            # Ensure token wasn't issued in the future (clock skew tolerance)
            now = datetime.now(timezone.utc).timestamp()
            if iat > now + 300:  # 5 minute tolerance
                logger.warning(f"JWT token issued in future: {iat} > {now}")
                return None
        
        # Query user
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        if user:
            logger.debug(f"Successfully authenticated user: {email}")
        else:
            logger.warning(f"User not found for email: {email}")
            
        return user
        
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        return None

def get_current_user_from_token(token: str, session: Session) -> Optional[User]:
    """Extract user from JWT token with proper validation."""
    if not token or not token.strip():
        return None
        
    try:
        # Decode JWT with expiration verification
        payload = jwt.decode(
            token.strip(), 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": True}
        )
        
        email = payload.get("sub")
        if not email:
            logger.warning(f"JWT token missing 'sub' claim")
            return None
            
        # Check expiration
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)):
            now = datetime.now(timezone.utc).timestamp()
            if exp < now:
                logger.warning(f"JWT token expired: {exp} < {now}")
                return None
        
        # Query user
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        return user
        
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        return None

def get_optional_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """Get user from authorization header if present."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    return get_current_user_from_token(token, session)


def get_current_user_required(
    user: Optional[User] = Depends(get_optional_user),
) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# --- Request/Response Models ---

class EstimateAddons(BaseModel):
    verification_requested: bool = False
    plot_requested: bool = False
    
    # Legacy / Frontend Compatibility
    ocr: bool = False
    voice: bool = False
    verify: bool = False 
    plot: bool = False

class CreditsEstimateRequest(BaseModel):
    tier: str # three_step, short, standard, research
    mode: str = "SOLVE" # SOLVE, VERIFY, etc.
    input_type: str = "text" # text, ocr_image, ocr_pdf, voice
    asset_type: str = "none"
    question_count: int = Field(default=1, ge=1, le=100)
    addons: EstimateAddons = Field(default_factory=EstimateAddons)
    graph_mode: Optional[str] = None

class CapChecks(BaseModel):
    daily_ok: bool
    ocr_ok: bool
    voice_ok: bool
    # could add others if needed

class CreditsEstimateBreakdown(BaseModel):
    base: float
    reason: str
    addons: Dict[str, float] = {}

class CreditsEstimateResponse(BaseModel):
    total_credits: float
    per_question_credits: float
    breakdown: CreditsEstimateBreakdown
    cap_checks: CapChecks
    pricing_version: str
    pricing_version_plan: str
    pricing_version_token_config: Optional[int] = None


class TransferRequest(BaseModel):
    recipient_email: str
    amount: Decimal = Field(gt=0)
    idempotency_key: str


class TransferResponse(BaseModel):
    transfer_id: str
    status: str
    amount: float
    recipient_email: str
    recipient_user_id: Optional[int] = None


class ClaimPendingResponse(BaseModel):
    claimed_count: int
    transfer_ids: List[str]


class CreditsBalanceResponse(BaseModel):
    spendable_balance: float
    pending_outgoing_total: float
    can_transfer: bool
    min_transfer: float
    max_transfer: float
    daily_remaining: float
    reason_if_disabled: Optional[str] = None
    credit_transfer_enabled: bool = False


# --- Logic ---
def _normalize_tier_key(raw_tier: str) -> Literal["free", "short", "standard", "research"]:
    return normalize_tier_key(raw_tier)


def _resolve_source_type(input_type: str, asset_type: str) -> Literal["text", "snap_image", "snap_pdf", "voice"]:
    input_key = (input_type or "").strip().lower()
    asset_key = (asset_type or "").strip().lower()
    if input_key == "voice":
        return "voice"
    if input_key == "snap":
        return "snap_pdf" if asset_key == "pdf" else "snap_image"
    return "text"



@router.post("/credits/estimate", response_model=CreditsEstimateResponse)
async def estimate_credits(
    body: CreditsEstimateRequest,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    # 1. Resolve pricing from active SOLVE prompt binding for the selected tier.
    subscription: Optional[Subscription] = None
    tier_key = _normalize_tier_key(body.tier)
    features, multipliers, binding = resolve_binding_pricing(session, tier_key)

    if user:
        from sqlmodel import select
        sub_query = (
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .where(Subscription.status == "active")
        )
        subscription = session.exec(sub_query).first()

    # 3. Determine Cost
    source_type = _resolve_source_type(body.input_type, body.asset_type)
    tier_config = getattr(multipliers.credits.solve, tier_key, None)
    if tier_config is None:
        raise HTTPException(status_code=500, detail=f"Missing tier pricing configuration for tier={tier_key}")

    if source_type == "snap_image":
        base_cost = float(tier_config.snap_image)
    elif source_type == "snap_pdf":
        base_cost = float(tier_config.snap_pdf)
    elif source_type == "voice":
        base_cost = float(tier_config.voice)
    else:
        base_cost = float(tier_config.text)

    reason_str = f"solve.{tier_key}.{source_type}"
        
    # Addons
    addons_cost = 0.0
    addon_detail = {}
    
    # Verification
    # Logic: If requested_mode is VERIFY, or addons.verification_requested is True?
    # Spec says mode="SOLVE|VERIFY...". If mode is SOLVE, verification might be an addon step?
    # User request: "addons": { "verification_requested": false ... }
    # Let's assume verification is post-solve addon or separate mode.
    # If mode=SOLVE and verify requested:
    verify_req = body.addons.verification_requested or body.addons.verify
    if verify_req and features.allow_verify:
        verify_cost = float(getattr(multipliers.credits.verify, tier_key, 0))
        addons_cost += verify_cost
        addon_detail["verify"] = verify_cost
        
    plot_req = body.addons.plot_requested or body.addons.plot
    if plot_req and features.allow_plot:
        plot_cost = float(multipliers.credits.plot_trigger)
        addons_cost += plot_cost
        addon_detail["plot"] = plot_cost

    per_question = base_cost + addons_cost
    total = per_question * body.question_count

    # 4. Cap Checks
    # We need usage data. If no user, assume OK.
    daily_ok = True
    ocr_ok = True
    voice_ok = True
    
    if user and subscription:
        usage = subscription.feature_usage or {}
        
        # Check Daily Cap (This is tricky without ledger/quota summary for 'today')
        # Assuming subscription.feature_usage tracks monthly/periodic usage, not daily.
        # But PlanFeatures has daily_credit_cap.
        # We might skip strictly checking daily limit here if we don't have the "used today" data readily available in feature_usage.
        # However, let's assume we want to signal if they are close or over if we knew. 
        # For now, let's mark true unless we implement a daily tracker lookup.
        # TODO: Implement accurate daily check via BillingLedger or dedicated counter
        pass 
        
        # Check Monthly Caps
        if body.input_type == "snap":
            current_ocr = usage.get("ocr", 0)
            if features.ocr_monthly_cap > 0 and current_ocr >= features.ocr_monthly_cap:
                ocr_ok = False
        
        if body.input_type == "voice":
            current_voice = usage.get("voice", 0)
            if features.voice_monthly_cap > 0 and current_voice >= features.voice_monthly_cap:
                voice_ok = False
                
    
    from app.services.pricing_service import pricing_service
    token_config_version = pricing_service.get_pricing_config(session).config_version_id
    return CreditsEstimateResponse(
        total_credits=total,
        per_question_credits=per_question,
        breakdown=CreditsEstimateBreakdown(
            base=base_cost,
            reason=reason_str,
            addons=addon_detail
        ),
        cap_checks=CapChecks(
            daily_ok=daily_ok,
            ocr_ok=ocr_ok,
            voice_ok=voice_ok
        ),
        pricing_version=str(multipliers.version),
        pricing_version_plan=str(multipliers.version),
        pricing_version_token_config=token_config_version
    )


@router.get("/credits/balance", response_model=CreditsBalanceResponse)
async def credits_balance(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_required),
):
    cfg = load_credit_transfer_config(session)
    view = credit_transfer_service.get_balance_view(session, user, cfg)
    return CreditsBalanceResponse(
        spendable_balance=float(view.spendable_balance),
        pending_outgoing_total=float(view.pending_outgoing_total),
        can_transfer=view.can_transfer,
        min_transfer=float(view.min_transfer),
        max_transfer=float(view.max_transfer),
        daily_remaining=float(view.daily_remaining),
        reason_if_disabled=view.reason_if_disabled,
        credit_transfer_enabled=view.credit_transfer_enabled,
    )


@router.post("/credits/transfer", response_model=TransferResponse)
async def transfer_credits(
    body: TransferRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_required),
):
    cfg = load_credit_transfer_config(session)
    try:
        transfer = credit_transfer_service.create_transfer(
            session,
            sender=user,
            recipient_email_raw=body.recipient_email,
            amount=body.amount,
            idempotency_key=body.idempotency_key,
            cfg=cfg,
            sender_ip=request.client.host if request.client else None,
        )

        if cfg.notifications_enabled:
            notification_service.create_notification(
                session,
                user_id=user.id,
                type="CREDIT_TRANSFER_SENT",
                title="Credit transfer submitted",
                body=f"Transferred {float(transfer.amount):.2f} credits to {transfer.recipient_email}.",
                severity="success",
                payload_json={"transfer_id": transfer.id, "status": transfer.status},
                dedupe_key=f"transfer_sent:{transfer.id}",
            )
            if transfer.recipient_user_id:
                notification_service.create_notification(
                    session,
                    user_id=transfer.recipient_user_id,
                    type="CREDIT_TRANSFER_RECEIVED",
                    title="Credits received",
                    body=f"You received {float(transfer.amount):.2f} credits from {user.email}.",
                    severity="success",
                    payload_json={"transfer_id": transfer.id, "sender_user_id": user.id},
                    dedupe_key=f"transfer_received:{transfer.id}",
                )
        session.commit()
    except CreditTransferError as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})
    except Exception:
        session.rollback()
        raise

    return TransferResponse(
        transfer_id=transfer.id,
        status=transfer.status,
        amount=float(transfer.amount),
        recipient_email=transfer.recipient_email,
        recipient_user_id=transfer.recipient_user_id,
    )


@router.post("/credits/claim_pending", response_model=ClaimPendingResponse)
async def claim_pending_credits(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_required),
):
    cfg = load_credit_transfer_config(session)
    if not cfg.enabled:
        raise HTTPException(status_code=503, detail={"code": "feature_disabled", "message": "Credit transfer is disabled"})

    claimed = credit_transfer_service.claim_pending_for_user(session, user)
    if cfg.notifications_enabled and claimed:
        for transfer in claimed:
            notification_service.create_notification(
                session,
                user_id=user.id,
                type="CREDIT_TRANSFER_CLAIMED",
                title="Pending credits claimed",
                body=f"You claimed {float(transfer.amount):.2f} credits.",
                severity="success",
                payload_json={"transfer_id": transfer.id},
                dedupe_key=f"transfer_claimed:{transfer.id}",
            )
    session.commit()
    return ClaimPendingResponse(claimed_count=len(claimed), transfer_ids=[t.id for t in claimed])
