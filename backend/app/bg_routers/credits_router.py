from typing import Dict, Any, Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from sqlalchemy import and_, func, or_
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timezone
import logging
from decimal import Decimal

from app.database import get_session
from app.models import (
    User,
    Subscription,
    CreditTransfer,
    CreditHoldV2,
    CreditLotV2,
    UsageLedgerV2,
    TopUpProduct,
    StripePriceMap,
    CreditHold,
    CreditLot,
)
from app.services.prompt_binding_pricing import normalize_tier_key, resolve_binding_pricing
from app.auth import SECRET_KEY, ALGORITHM
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.credit_transfer_service import credit_transfer_service, CreditTransferError
from app.services.notification_service import notification_service
from app.services.solve.single_task_parser import parse_single_question_tasks
from app.jobs.nightly_reconciliation import compute_user_balance
from app.admin_billing.deps import get_current_user as get_current_user_strict
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
    tier: str # short_steps, final, standard, research (legacy free/short accepted)
    mode: str = "SOLVE" # SOLVE, VERIFY, etc.
    input_type: str = "text" # text, ocr_image, ocr_pdf, voice
    asset_type: str = "none"
    question_count: int = Field(default=1, ge=1, le=100)
    addons: EstimateAddons = Field(default_factory=EstimateAddons)
    graph_mode: Optional[str] = None
    include_attempt_fee: bool = False
    openai_call_expected: bool = False
    # Single-question workload bundle (preferred)
    original_input_text: Optional[str] = None
    context_text: Optional[str] = None
    tasks: Optional[List[Dict[str, Any]]] = None
    selected_task_ids: Optional[List[str]] = None
    user_action: Optional[str] = None
    detection_confidence: Optional[str] = None
    solve_mode: Optional[str] = None

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
    max_questions_allowed: Optional[int] = None
    # Workload-based fields (single-question with tasks)
    context_credits: Optional[float] = None
    per_task_credits: Optional[Dict[str, float]] = None
    bundle_factor: Optional[float] = None
    estimated_total_credits: Optional[float] = None
    selected_task_ids: Optional[List[str]] = None
    breakdown_reasons: Optional[Dict[str, List[str]]] = None
    solve_mode: Optional[str] = None
    tasks_truncated: Optional[bool] = None
    tasks_truncated_from: Optional[int] = None


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
    user_id: int
    available_credits: float
    reserved_credits: float
    expiring_soon_credits: float
    lots_summary: Dict[str, float]
    spendable_balance: float
    pending_outgoing_total: float
    can_transfer: bool
    min_transfer: float
    max_transfer: float
    daily_remaining: float
    reason_if_disabled: Optional[str] = None
    credit_transfer_enabled: bool = False


class CursorPage(BaseModel):
    items: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    limit: int


def _decode_cursor(cursor: Optional[str]) -> tuple[Optional[datetime], Optional[str]]:
    if not cursor:
        return None, None
    try:
        created_raw, entity_id = cursor.split("|", 1)
        return datetime.fromisoformat(created_raw), entity_id
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


def _encode_cursor(created_at: datetime, entity_id: str) -> str:
    return f"{created_at.isoformat()}|{entity_id}"


# --- Logic ---
def _normalize_tier_key(raw_tier: str) -> Literal["short_steps", "final", "standard", "research"]:
    return normalize_tier_key(raw_tier)


def _resolve_source_type(input_type: str, asset_type: str) -> Literal["text", "snap_image", "snap_pdf", "voice"]:
    input_key = (input_type or "").strip().lower()
    asset_key = (asset_type or "").strip().lower()
    if input_key == "voice":
        return "voice"
    if input_key == "snap":
        return "snap_pdf" if asset_key == "pdf" else "snap_image"
    return "text"


def _binding_costs(binding: Optional[Any], tier_key: str) -> Dict[str, float]:
    if not binding:
        return {
            "text": 0.0,
            "snap_image": 0.0,
            "snap_pdf": 0.0,
            "voice": 0.0,
            "verify_addon": 0.0,
            "plot_addon": 0.0,
            "attempt_fee": 0.0,
        }

    multipliers = (getattr(binding, "multipliers", None) or {}) if binding else {}
    credits = multipliers.get("credits") if isinstance(multipliers, dict) else {}
    solve = credits.get("solve") if isinstance(credits, dict) else {}
    tier_cfg = solve.get(tier_key) if isinstance(solve, dict) else {}
    verify_map = credits.get("verify") if isinstance(credits, dict) else {}
    attempt_map = credits.get("attempt_fee") if isinstance(credits, dict) else {}
    fallback = {
        "text": float((tier_cfg or {}).get("text") or 0),
        "snap_image": float((tier_cfg or {}).get("snap_image") or 0),
        "snap_pdf": float((tier_cfg or {}).get("snap_pdf") or 0),
        "voice": float((tier_cfg or {}).get("voice") or 0),
        "verify_addon": float((verify_map or {}).get(tier_key) or 0),
        "plot_addon": float((credits or {}).get("plot_trigger") or 0),
        "attempt_fee": float((attempt_map or {}).get(tier_key) or 0),
    }
    return {
        # Use dedicated columns when present; fallback per field to multipliers.
        "text": float(binding.solve_text_cost) if getattr(binding, "solve_text_cost", None) is not None else fallback["text"],
        "snap_image": float(binding.solve_snap_image_cost) if getattr(binding, "solve_snap_image_cost", None) is not None else fallback["snap_image"],
        "snap_pdf": float(binding.solve_snap_pdf_cost) if getattr(binding, "solve_snap_pdf_cost", None) is not None else fallback["snap_pdf"],
        "voice": float(binding.solve_voice_cost) if getattr(binding, "solve_voice_cost", None) is not None else fallback["voice"],
        "verify_addon": float(binding.verify_addon_cost) if getattr(binding, "verify_addon_cost", None) is not None else fallback["verify_addon"],
        "plot_addon": float(binding.plot_addon_cost) if getattr(binding, "plot_addon_cost", None) is not None else fallback["plot_addon"],
        "attempt_fee": float(binding.attempt_fee) if getattr(binding, "attempt_fee", None) is not None else fallback["attempt_fee"],
    }



@router.post("/credits/estimate", response_model=CreditsEstimateResponse)
async def estimate_credits(
    body: CreditsEstimateRequest,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    if int(body.question_count or 1) != 1:
        raise HTTPException(status_code=400, detail="Only one question per solve is allowed.")

    max_tasks_allowed_global = 15
    detected_task_count_raw = 0
    if isinstance(body.tasks, list) and body.tasks:
        detected_task_count_raw = len(body.tasks)
    else:
        parsed = parse_single_question_tasks(
            str(body.original_input_text or body.context_text or ""),
            max_tasks=max_tasks_allowed_global,
        )
        detected_task_count_raw = int(parsed.get("detected_task_count_raw") or 0)
    if detected_task_count_raw > max_tasks_allowed_global:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_tasks_allowed_global} tasks per question.",
        )

    # 1. Resolve pricing from active SOLVE prompt binding for the selected tier.
    subscription: Optional[Subscription] = None
    requested_tier_key = _normalize_tier_key(body.tier)
    tier_key = requested_tier_key
    if requested_tier_key in {"short_steps", "final"} and detected_task_count_raw > 3:
        tier_key = "standard"
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
    costs = _binding_costs(binding, tier_key)
    base_key = source_type if source_type in {"text", "snap_image", "snap_pdf", "voice"} else "text"
    base_cost = float(costs.get(base_key, 0.0))

    reason_str = f"solve.{tier_key}.{source_type}"
    if tier_key != requested_tier_key:
        reason_str += ".tier_forced_standard"
        
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
        verify_cost = float(costs.get("verify_addon", 0.0))
        addons_cost += verify_cost
        addon_detail["verify"] = verify_cost
        
    plot_req = body.addons.plot_requested or body.addons.plot
    if plot_req and features.allow_plot:
        plot_cost = float(costs.get("plot_addon", 0.0))
        addons_cost += plot_cost
        addon_detail["plot"] = plot_cost

    attempt_fee = 0.0
    if body.include_attempt_fee or body.openai_call_expected:
        attempt_fee = float(costs.get("attempt_fee", 0.0))
        addons_cost += attempt_fee
        addon_detail["attempt_fee"] = attempt_fee

    per_question = base_cost + addons_cost
    total = per_question * body.question_count
    workload_payload: Dict[str, Any] = {}
    max_tasks_allowed = max_tasks_allowed_global

    # Workload-based estimate for single-question task bundles.
    if body.tasks is not None or body.context_text is not None or body.original_input_text is not None:
        from app.services.workload_credit_estimator import estimate_task_bundle_credits

        raw_tasks = list(body.tasks or [])
        selected_task_ids = [str(t) for t in (body.selected_task_ids or []) if str(t).strip()]
        if not raw_tasks:
            implicit_text = str(body.original_input_text or body.context_text or "")
            raw_tasks = [{"task_id": "t1", "task_text": implicit_text, "order_index": 1}]
            if not selected_task_ids:
                selected_task_ids = ["t1"]

        capped_tasks = raw_tasks[:max_tasks_allowed]
        for idx, t in enumerate(capped_tasks, start=1):
            t["task_id"] = f"t{idx}"
            t["order_index"] = idx

        if not selected_task_ids:
            selected_task_ids = [str(t.get("task_id")) for t in capped_tasks if str(t.get("task_id") or "").strip()]

        est = estimate_task_bundle_credits(
            context_text=str(body.context_text or body.original_input_text or ""),
            tasks=capped_tasks,
            selected_task_ids=selected_task_ids,
        )
        # Additive pricing contract:
        # total = base + addons + workload(task bundle)
        workload_total = float(est.get("estimated_total_credits") or 0.0)
        total = float(total) + workload_total
        per_question = total
        workload_payload = {
            "context_credits": float(est.get("context_credits") or 0.0),
            "per_task_credits": est.get("per_task_credits") or {},
            "bundle_factor": float(est.get("bundle_factor") or 0.85),
            # Keep this aligned to what UI shows as final estimate.
            "estimated_total_credits": float(total),
            "selected_task_ids": est.get("selected_task_ids") or [],
            "breakdown_reasons": est.get("breakdown_reasons") or {},
            "solve_mode": (body.solve_mode or ("BUNDLE_COMBINED" if body.user_action == "combined_solution" else "PER_TASK_STEPS")),
            "tasks_truncated": len(raw_tasks) > len(capped_tasks),
            "tasks_truncated_from": len(raw_tasks) if len(raw_tasks) > len(capped_tasks) else None,
        }

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
        pricing_version_token_config=token_config_version,
        max_questions_allowed=(int(getattr(binding, "max_questions_allowed", 0) or 0) or None),
        context_credits=workload_payload.get("context_credits"),
        per_task_credits=workload_payload.get("per_task_credits"),
        bundle_factor=workload_payload.get("bundle_factor"),
        estimated_total_credits=workload_payload.get("estimated_total_credits"),
        selected_task_ids=workload_payload.get("selected_task_ids"),
        breakdown_reasons=workload_payload.get("breakdown_reasons"),
        solve_mode=workload_payload.get("solve_mode"),
        tasks_truncated=workload_payload.get("tasks_truncated"),
        tasks_truncated_from=workload_payload.get("tasks_truncated_from"),
    )


@router.get("/credits/balance", response_model=CreditsBalanceResponse)
async def credits_balance(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_strict),
):
    cfg = load_credit_transfer_config(session)
    view = credit_transfer_service.get_balance_view(session, user, cfg)

    # Authoritative solve billing path uses legacy CreditLot/CreditHold + BillingLedger.
    # UI balance must follow that same source to reflect solver deductions correctly.
    authoritative_available = Decimal(str(compute_user_balance(session, user.id)))
    reserved = session.exec(
        select(func.coalesce(func.sum(CreditHold.reserved_credits), 0))
        .where(CreditHold.user_id == user.id)
        .where(CreditHold.status == "held")
    ).one()
    now = datetime.utcnow()
    soon_cutoff = now + __import__("datetime").timedelta(days=30)
    expiring = session.exec(
        select(func.coalesce(func.sum(CreditLot.credits_remaining), 0))
        .where(CreditLot.user_id == user.id)
        .where(CreditLot.status == "ACTIVE")
        .where(CreditLot.credits_remaining > 0)
        .where(CreditLot.expires_at != None)
        .where(CreditLot.expires_at >= now)
        .where(CreditLot.expires_at <= soon_cutoff)
    ).one()
    lots_count = session.exec(select(func.count(CreditLot.id)).where(CreditLot.user_id == user.id)).one()
    active_lots = session.exec(
        select(func.count(CreditLot.id))
        .where(CreditLot.user_id == user.id)
        .where(CreditLot.status == "ACTIVE")
        .where(CreditLot.credits_remaining > 0)
    ).one()

    effective_available = authoritative_available

    return CreditsBalanceResponse(
        user_id=user.id,
        available_credits=float(effective_available),
        reserved_credits=float(reserved),
        expiring_soon_credits=float(expiring),
        lots_summary={"total_lots": float(lots_count), "active_lots": float(active_lots)},
        spendable_balance=float(effective_available),
        pending_outgoing_total=float(view.pending_outgoing_total),
        can_transfer=view.can_transfer,
        min_transfer=float(view.min_transfer),
        max_transfer=float(view.max_transfer),
        daily_remaining=float(view.daily_remaining),
        reason_if_disabled=view.reason_if_disabled,
        credit_transfer_enabled=view.credit_transfer_enabled,
    )


@router.get("/credits/holds", response_model=CursorPage)
async def credits_holds(
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    cursor: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_strict),
):
    cursor_dt, cursor_id = _decode_cursor(cursor)
    q = select(CreditHoldV2).where(CreditHoldV2.user_id == user.id)
    if status:
        q = q.where(CreditHoldV2.status == status.lower())
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                CreditHoldV2.created_at < cursor_dt,
                and_(CreditHoldV2.created_at == cursor_dt, CreditHoldV2.hold_id < cursor_id),
            )
        )
    rows = session.exec(q.order_by(CreditHoldV2.created_at.desc(), CreditHoldV2.hold_id.desc()).limit(int(limit) + 1)).all()
    has_more = len(rows) > int(limit)
    rows = rows[: int(limit)]
    items = [
        {
            "hold_id": r.hold_id,
            "status": r.status,
            "reserved": float(r.amount_reserved),
            "settled": float(r.amount_settled),
            "released": float(r.amount_released),
            "created_at": r.created_at,
            "expires_at": r.expires_at,
            "tier": r.tier,
            "action": r.action,
            "request_id": r.request_id,
            "attempt_id": r.attempt_id,
        }
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].hold_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=int(limit))


@router.get("/credits/ledger", response_model=CursorPage)
async def credits_ledger(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_strict),
):
    cursor_dt, cursor_id = _decode_cursor(cursor)
    q = select(UsageLedgerV2).where(UsageLedgerV2.user_id == user.id)
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                UsageLedgerV2.created_at < cursor_dt,
                and_(UsageLedgerV2.created_at == cursor_dt, UsageLedgerV2.ledger_id < cursor_id),
            )
        )
    rows = session.exec(q.order_by(UsageLedgerV2.created_at.desc(), UsageLedgerV2.ledger_id.desc()).limit(int(limit) + 1)).all()
    has_more = len(rows) > int(limit)
    rows = rows[: int(limit)]
    items = [
        {
            "ledger_id": r.ledger_id,
            "tier": r.tier,
            "action": r.action,
            "question_index": r.question_index,
            "total_cost": float(r.total_cost),
            "outcome": r.outcome,
            "created_at": r.created_at,
            "request_id": r.request_id,
            "attempt_id": r.attempt_id,
        }
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].ledger_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=int(limit))


@router.get("/credits/lots", response_model=CursorPage)
async def credits_lots(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_strict),
):
    cursor_dt, cursor_id = _decode_cursor(cursor)
    q = select(CreditLotV2).where(CreditLotV2.user_id == user.id)
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                CreditLotV2.created_at < cursor_dt,
                and_(CreditLotV2.created_at == cursor_dt, CreditLotV2.lot_id < cursor_id),
            )
        )
    rows = session.exec(q.order_by(CreditLotV2.created_at.desc(), CreditLotV2.lot_id.desc()).limit(int(limit) + 1)).all()
    has_more = len(rows) > int(limit)
    rows = rows[: int(limit)]
    items = [
        {
            "lot_id": r.lot_id,
            "source": r.source,
            "credits_total": float(r.credits_total),
            "credits_remaining": float(r.credits_remaining),
            "expires_at": r.expires_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].lot_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=int(limit))


@router.get("/credits/packs")
async def credits_packs(
    session: Session = Depends(get_session),
):
    packs = session.exec(select(TopUpProduct).where(TopUpProduct.is_active == True).order_by(TopUpProduct.credits.asc())).all()
    mappings = session.exec(select(StripePriceMap).where(StripePriceMap.kind == "TOPUP").where(StripePriceMap.active == True)).all()
    by_code = {m.internal_code: m.stripe_price_id for m in mappings}
    items = []
    for idx, p in enumerate(packs):
        meta = p.metadata_json or {}
        label = str(meta.get("label") or "")
        items.append(
            {
                "pack_code": p.code,
                "credits": p.credits,
                "label": label,
                "active": p.is_active,
                "sort_order": idx + 1,
                "display_name": p.name or p.code.replace("_", " ").title(),
                "stripe_mapping": {
                    "stripe_price_id": by_code.get(p.code),
                    "mapped": bool(by_code.get(p.code)),
                },
            }
        )
    return {"items": items}


@router.post("/credits/transfer", response_model=TransferResponse)
async def transfer_credits(
    body: TransferRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_strict),
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
    user: User = Depends(get_current_user_strict),
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
