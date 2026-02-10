from typing import Dict, Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlmodel import Session
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timezone
import logging

from app.database import get_session
from app.models import User, Subscription, Plan
from app.schemas.pricing import PlanMultipliers, PlanFeatures, CreditsConfig
from app.auth import SECRET_KEY, ALGORITHM
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
        from sqlmodel import select
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
    except JWTClaimsError as e:
        logger.warning(f"JWT claims error: {e}")
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
        from sqlmodel import select
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        return user
        
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except JWTClaimsError as e:
        logger.warning(f"JWT claims error: {e}")
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


# --- Logic ---

@router.post("/credits/estimate", response_model=CreditsEstimateResponse)
async def estimate_credits(
    body: CreditsEstimateRequest,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    # 1. Resolve Plan
    plan: Plan = None
    subscription: Optional[Subscription] = None
    
    if user:
        # Load subscription
        from sqlmodel import select
        # Assuming user.subscription is a relationship, or we query it.
        # User <-> Subscription is usually 1:1
        # Let's query active subscription
        sub_query = select(Subscription).where(Subscription.user_id == user.id).where(Subscription.is_active == True)
        subscription = session.exec(sub_query).first()
        
        if subscription:
            # Query plan
            plan = session.get(Plan, subscription.plan_id)
    
    if not plan:
        # Fallback to default "Free" plan if no user or no subscription
        # Ideally we fetch the "free" plan from DB
        from sqlmodel import select
        plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
        if not plan:
             raise HTTPException(status_code=500, detail="Default pricing plan not found.")

    # 2. Parse Schemas
    try:
        multipliers = PlanMultipliers(**(plan.multipliers or {}))
        features = PlanFeatures(**(plan.features or {}))
    except Exception as e:
        # Fallback for legacy plans?
        # print(f"Schema parse error: {e}")
        # Create default generic structure
        multipliers = PlanMultipliers()
        features = PlanFeatures()

    # 3. Determine Cost
    # Map input tier (string) to config key
    raw_tier = body.tier.lower()
    if raw_tier in {"three_step", "free"}:
        tier_key = "three_step"
    elif raw_tier in {"short"}:
        tier_key = "short"
    elif raw_tier in {"standard"}:
        tier_key = "standard"
    elif raw_tier in {"research"}:
        tier_key = "research"
    else:
        tier_key = "standard"
    
    # Flat credits per solve (business rule)
    tier_costs = {
        "three_step": 5.0,
        "short": 7.0,
        "standard": 10.0,
        "research": 25.0,
    }
    base_cost = tier_costs.get(tier_key, 10.0)
    reason_str = f"solve.{tier_key}.flat"
        
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
        addon_detail["verify"] = 0.0
        
    plot_req = body.addons.plot_requested or body.addons.plot
    if plot_req and features.allow_plot:
        addon_detail["plot"] = 0.0

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
