from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from app.admin_billing.deps import get_current_user
from app.database import get_session
from app.models import (
    BillingLedger,
    CreditHold,
    CreditLot,
    CreditHoldAllocationV2,
    CreditHoldV2,
    CreditLotV2,
    PromptBinding,
    PromptModeEnum,
    PromptTierEnum,
    StripePriceMap,
    Subscription,
    TopUpProduct,
    TrimStrategyEnum,
    UsageLedger,
    UsageLedgerV2,
    User,
)
from app.services.audit_log_service import audit_log_service
from app.services.credit_billing_service import credit_billing_service


router = APIRouter(prefix="/api/v1/admin/credits", tags=["admin-credits"])
prompt_bindings_router = APIRouter(prefix="/api/v1/admin/prompt_bindings", tags=["admin-prompt-bindings"])


ALL_ADMIN_ROLES = {"superadmin", "admin", "support", "finance", "devops"}
WRITE_PACK_ROLES = {"superadmin", "admin"}
GRANT_ROLES = {"superadmin", "admin"}


def _role(user: User) -> str:
    return str((user.role or "")).strip().lower()


def _require_roles(user: User, allowed: set[str], message: str = "Forbidden") -> None:
    if _role(user) not in allowed:
        raise HTTPException(status_code=403, detail=message)


def _require_admin_read(user: User) -> None:
    _require_roles(user, ALL_ADMIN_ROLES, "Admin billing access required")


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


def _detect_channel(*, request_id: Optional[str], action: Optional[str], meta: Optional[dict] = None) -> str:
    rid = str(request_id or "").strip().lower()
    act = str(action or "").strip().lower()
    meta_obj = meta if isinstance(meta, dict) else {}
    meta_channel = str(meta_obj.get("channel") or "").strip().lower()
    if meta_channel in {"whatsapp", "app"}:
        return meta_channel
    if rid.startswith("wa-") or rid.startswith("wa:") or "whatsapp" in act:
        return "whatsapp"
    return "app"


class CursorPage(BaseModel):
    items: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    limit: int
    total: Optional[int] = None


class GrantCreditsBody(BaseModel):
    user_id: int
    credits: Decimal = Field(gt=0)
    expires_at: Optional[datetime] = None
    reason: str


class ReleaseHoldBody(BaseModel):
    reason: str


class PatchPackBody(BaseModel):
    active: Optional[bool] = None
    sort_order: Optional[int] = None
    label: Optional[str] = None
    display_name: Optional[str] = None
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    reason: str


class PatchPromptBindingBody(BaseModel):
    tier: Optional[PromptTierEnum] = None
    mode: Optional[PromptModeEnum] = None
    global_system_prompt_id: Optional[str] = None
    developer_prompt_id: Optional[str] = None
    output_schema_id: Optional[str] = None
    openai_prompt_id: Optional[str] = None
    openai_prompt_version: Optional[str] = None
    openai_prompt_use_latest: Optional[bool] = None
    openai_prompt_variable_mapping: Optional[Dict[str, Any]] = None
    openai_prompt_cache_key_template: Optional[str] = None
    openai_prompt_cache_retention: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    multipliers: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    max_questions_allowed: Optional[int] = None
    timeout_ms: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    system_schema_budget_tokens: Optional[int] = None
    context_budget_tokens: Optional[int] = None
    json_retry_max_output_tokens: Optional[int] = None
    json_retry_max_attempts: Optional[int] = None
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None
    plot_annotations_cap: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    trim_strategy: Optional[TrimStrategyEnum] = None
    max_steps: Optional[int] = None
    retry_cap_tokens: Optional[int] = None
    solve_text_cost: Optional[Decimal] = None
    solve_snap_image_cost: Optional[Decimal] = None
    solve_snap_pdf_cost: Optional[Decimal] = None
    solve_voice_cost: Optional[Decimal] = None
    verify_addon_cost: Optional[Decimal] = None
    plot_addon_cost: Optional[Decimal] = None
    attempt_fee: Optional[Decimal] = None
    reason: str


@router.get("/user")
def admin_lookup_credit_user(
    query: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    q = query.strip()
    user: Optional[User] = None
    if q.isdigit():
        user = session.get(User, int(q))
    if not user:
        user = session.exec(select(User).where(User.email == q)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    available = session.exec(
        select(func.coalesce(func.sum(CreditLotV2.credits_remaining), 0)).where(CreditLotV2.user_id == user.id)
    ).one()
    reserved = session.exec(
        select(func.coalesce(func.sum(CreditHoldV2.amount_reserved - CreditHoldV2.amount_settled - CreditHoldV2.amount_released), 0))
        .where(CreditHoldV2.user_id == user.id)
        .where(CreditHoldV2.status == "active")
    ).one()
    lots_count = session.exec(select(func.count(CreditLotV2.lot_id)).where(CreditLotV2.user_id == user.id)).one()
    holds_count = session.exec(select(func.count(CreditHoldV2.hold_id)).where(CreditHoldV2.user_id == user.id)).one()
    ledger_count = session.exec(select(func.count(UsageLedgerV2.ledger_id)).where(UsageLedgerV2.user_id == user.id)).one()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "role": user.role,
        },
        "credits": {
            "available_credits": float(available),
            "reserved_credits": float(reserved),
            "lots_count": int(lots_count),
            "holds_count": int(holds_count),
            "ledger_count": int(ledger_count),
        },
    }


@router.get("/ledger", response_model=CursorPage)
def admin_credits_ledger(
    user_id: Optional[int] = None,
    request_id: Optional[str] = None,
    tier: Optional[str] = None,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    cursor_dt, cursor_id = _decode_cursor(cursor)

    q = select(UsageLedgerV2)
    count_q = select(func.count(UsageLedgerV2.ledger_id))
    if user_id is not None:
        q = q.where(UsageLedgerV2.user_id == user_id)
        count_q = count_q.where(UsageLedgerV2.user_id == user_id)
    if request_id:
        q = q.where(UsageLedgerV2.request_id == request_id.strip())
        count_q = count_q.where(UsageLedgerV2.request_id == request_id.strip())
    if tier:
        q = q.where(UsageLedgerV2.tier == tier.upper())
        count_q = count_q.where(UsageLedgerV2.tier == tier.upper())
    if action:
        q = q.where(UsageLedgerV2.action == action)
        count_q = count_q.where(UsageLedgerV2.action == action)
    if outcome:
        q = q.where(UsageLedgerV2.outcome == outcome)
        count_q = count_q.where(UsageLedgerV2.outcome == outcome)
    if date_from:
        q = q.where(UsageLedgerV2.created_at >= date_from)
        count_q = count_q.where(UsageLedgerV2.created_at >= date_from)
    if date_to:
        q = q.where(UsageLedgerV2.created_at <= date_to)
        count_q = count_q.where(UsageLedgerV2.created_at <= date_to)
    total = int(session.exec(count_q).one() or 0)
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                UsageLedgerV2.created_at < cursor_dt,
                and_(UsageLedgerV2.created_at == cursor_dt, UsageLedgerV2.ledger_id < cursor_id),
            )
        )
    rows = session.exec(q.order_by(UsageLedgerV2.created_at.desc(), UsageLedgerV2.ledger_id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    user_ids = {r.user_id for r in rows}
    user_email_map: Dict[int, str] = {}
    if user_ids:
        users = session.exec(select(User).where(User.id.in_(user_ids))).all()
        user_email_map = {int(u.id): u.email for u in users if u.id is not None}

    items = [
        {
            "ledger_id": r.ledger_id,
            "user_id": r.user_id,
            "user_email": user_email_map.get(r.user_id),
            "hold_id": r.hold_id,
            "request_id": r.request_id,
            "attempt_id": r.attempt_id,
            "idempotency_key": r.idempotency_key,
            "tier": r.tier,
            "action": r.action,
            "question_id": r.question_id,
            "question_index": r.question_index,
            "base_cost": float(r.base_cost),
            "addons_cost": float(r.addons_cost),
            "attempt_fee": float(r.attempt_fee),
            "total_cost": float(r.total_cost),
            "balance_after": None,
            "channel": _detect_channel(
                request_id=r.request_id,
                action=r.action,
                meta=(r.pricing_snapshot if isinstance(r.pricing_snapshot, dict) else {}),
            ),
            "outcome": r.outcome,
            "pricing_snapshot": r.pricing_snapshot,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    if items:
        next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].ledger_id) if has_more and rows else None
        return CursorPage(items=items, next_cursor=next_cursor, limit=limit, total=total)

    # Legacy fallback for environments still writing to BillingLedger/CreditHold/UsageLedger.
    legacy_q = select(BillingLedger)
    legacy_count_q = select(func.count(BillingLedger.id))
    if user_id is not None:
        legacy_q = legacy_q.where(BillingLedger.user_id == user_id)
        legacy_count_q = legacy_count_q.where(BillingLedger.user_id == user_id)
    if request_id:
        legacy_q = legacy_q.where(BillingLedger.request_id == request_id.strip())
        legacy_count_q = legacy_count_q.where(BillingLedger.request_id == request_id.strip())
    if tier:
        legacy_q = legacy_q.where(BillingLedger.tier == tier.upper())
        legacy_count_q = legacy_count_q.where(BillingLedger.tier == tier.upper())
    if action:
        legacy_q = legacy_q.where(BillingLedger.action_type == action)
        legacy_count_q = legacy_count_q.where(BillingLedger.action_type == action)
    if outcome:
        legacy_q = legacy_q.where(BillingLedger.status == outcome.upper())
        legacy_count_q = legacy_count_q.where(BillingLedger.status == outcome.upper())
    if date_from:
        legacy_q = legacy_q.where(BillingLedger.created_at >= date_from)
        legacy_count_q = legacy_count_q.where(BillingLedger.created_at >= date_from)
    if date_to:
        legacy_q = legacy_q.where(BillingLedger.created_at <= date_to)
        legacy_count_q = legacy_count_q.where(BillingLedger.created_at <= date_to)

    legacy_total = int(session.exec(legacy_count_q).one() or 0)
    legacy_cursor_id_int: Optional[int] = None
    if cursor_id and cursor_id.startswith("legacy_billing_"):
        try:
            legacy_cursor_id_int = int(cursor_id.replace("legacy_billing_", ""))
        except Exception:
            legacy_cursor_id_int = None
    if cursor_dt and legacy_cursor_id_int is not None:
        legacy_q = legacy_q.where(
            or_(
                BillingLedger.created_at < cursor_dt,
                and_(BillingLedger.created_at == cursor_dt, BillingLedger.id < legacy_cursor_id_int),
            )
        )

    legacy_rows = session.exec(
        legacy_q.order_by(BillingLedger.created_at.desc(), BillingLedger.id.desc()).limit(limit + 1)
    ).all()
    legacy_has_more = len(legacy_rows) > limit
    legacy_rows = legacy_rows[:limit]
    legacy_user_ids = {r.user_id for r in legacy_rows if r.user_id is not None}
    legacy_user_email_map: Dict[int, str] = {}
    if legacy_user_ids:
        legacy_users = session.exec(select(User).where(User.id.in_(legacy_user_ids))).all()
        legacy_user_email_map = {int(u.id): u.email for u in legacy_users if u.id is not None}

    legacy_items: List[Dict[str, Any]] = []
    for r in legacy_rows:
        snap = r.pricing_snapshot_json if isinstance(r.pricing_snapshot_json, dict) else {}
        base_cost = float(snap.get("base_cost") or snap.get("solve_base_cost") or 0)
        addons_cost = float(snap.get("addons_cost") or snap.get("plot_addon_cost") or snap.get("verify_addon_cost") or 0)
        attempt_fee_cost = float(snap.get("attempt_fee") or 0)
        total_cost = float(r.credits_charged or 0)
        if base_cost == 0 and addons_cost == 0 and attempt_fee_cost == 0 and total_cost > 0:
            # Legacy BillingLedger does not always store a pricing snapshot breakdown.
            base_cost = total_cost

        legacy_items.append(
            {
                "ledger_id": f"legacy_billing_{r.id}",
                "user_id": r.user_id,
                "user_email": legacy_user_email_map.get(r.user_id),
                "hold_id": None,
                "request_id": r.request_id,
                "attempt_id": None,
                "idempotency_key": r.idempotency_key,
                "tier": r.tier,
                "action": r.action_type,
                "question_id": r.question_id,
                "question_index": None,
                "base_cost": base_cost,
                "addons_cost": addons_cost,
                "attempt_fee": attempt_fee_cost,
                "total_cost": total_cost,
                "balance_after": float(r.credits_after or 0),
                "channel": _detect_channel(
                    request_id=r.request_id,
                    action=r.action_type,
                    meta=snap,
                ),
                "outcome": (r.status or "").lower() or "charged",
                "pricing_snapshot": snap,
                "created_at": r.created_at,
            }
        )

    legacy_usage_q = (
        select(UsageLedger, Subscription.user_id)
        .join(Subscription, Subscription.id == UsageLedger.subscription_id)
        .where(UsageLedger.transaction_type == "DEBIT")
    )
    if user_id is not None:
        legacy_usage_q = legacy_usage_q.where(Subscription.user_id == user_id)
    if request_id:
        legacy_usage_q = legacy_usage_q.where(UsageLedger.reference_id == request_id.strip())
    if date_from:
        legacy_usage_q = legacy_usage_q.where(UsageLedger.created_at >= date_from)
    if date_to:
        legacy_usage_q = legacy_usage_q.where(UsageLedger.created_at <= date_to)
    if cursor_dt:
        legacy_usage_q = legacy_usage_q.where(UsageLedger.created_at <= cursor_dt)

    usage_rows = session.exec(
        legacy_usage_q.order_by(UsageLedger.created_at.desc(), UsageLedger.id.desc()).limit(limit * 3)
    ).all()
    usage_user_ids = {int(uid) for _, uid in usage_rows if uid is not None}
    usage_user_email_map: Dict[int, str] = {}
    if usage_user_ids:
        usage_users = session.exec(select(User).where(User.id.in_(usage_user_ids))).all()
        usage_user_email_map = {int(u.id): u.email for u in usage_users if u.id is not None}

    usage_items: List[Dict[str, Any]] = []
    for usage_row, usage_user_id in usage_rows:
        meta_obj = usage_row.meta if isinstance(usage_row.meta, dict) else {}
        req_id = str(usage_row.reference_id or "")
        tier_token = str(meta_obj.get("requested_tier") or meta_obj.get("tier") or "").strip().upper() or None
        action_token = str(meta_obj.get("action") or "").strip().lower() or None
        if not action_token:
            action_token = "whatsapp_solve" if _detect_channel(request_id=req_id, action="", meta=meta_obj) == "whatsapp" else "solve"
        if tier and tier_token and tier_token != tier.upper():
            continue
        if action and action_token != action:
            continue
        usage_items.append(
            {
                "ledger_id": f"legacy_usage_{usage_row.id}",
                "user_id": int(usage_user_id),
                "user_email": usage_user_email_map.get(int(usage_user_id)),
                "hold_id": None,
                "request_id": req_id or None,
                "attempt_id": None,
                "idempotency_key": None,
                "tier": tier_token,
                "action": action_token,
                "question_id": None,
                "question_index": None,
                "base_cost": float(usage_row.amount or 0),
                "addons_cost": 0.0,
                "attempt_fee": 0.0,
                "total_cost": float(usage_row.amount or 0),
                "balance_after": float(usage_row.balance_after or 0),
                "channel": _detect_channel(
                    request_id=req_id,
                    action=action_token,
                    meta=meta_obj,
                ),
                "outcome": "charged",
                "pricing_snapshot": meta_obj,
                "created_at": usage_row.created_at,
            }
        )

    combined_items = legacy_items + usage_items
    if cursor_dt and cursor_id:
        combined_items = [
            i
            for i in combined_items
            if (i.get("created_at") < cursor_dt)
            or (i.get("created_at") == cursor_dt and str(i.get("ledger_id")) < str(cursor_id))
        ]
    combined_items.sort(key=lambda i: (i.get("created_at"), str(i.get("ledger_id"))), reverse=True)
    combined_page = combined_items[:limit]
    combined_has_more = len(combined_items) > limit
    if combined_page:
        next_cursor = (
            _encode_cursor(combined_page[-1]["created_at"], str(combined_page[-1]["ledger_id"]))
            if combined_has_more
            else None
        )
        return CursorPage(
            items=combined_page,
            next_cursor=next_cursor,
            limit=limit,
            total=legacy_total + len(usage_items),
        )

    legacy_next_cursor = (
        _encode_cursor(legacy_rows[-1].created_at, f"legacy_billing_{legacy_rows[-1].id}")
        if legacy_has_more and legacy_rows
        else None
    )
    return CursorPage(items=legacy_items, next_cursor=legacy_next_cursor, limit=limit, total=legacy_total)


@router.get("/holds", response_model=CursorPage)
def admin_credits_holds(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    cursor_dt, cursor_id = _decode_cursor(cursor)

    q = select(CreditHoldV2)
    if status:
        q = q.where(CreditHoldV2.status == status.lower())
    if tier:
        q = q.where(CreditHoldV2.tier == tier.upper())
    if user_id is not None:
        q = q.where(CreditHoldV2.user_id == user_id)
    if date_from:
        q = q.where(CreditHoldV2.created_at >= date_from)
    if date_to:
        q = q.where(CreditHoldV2.created_at <= date_to)
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                CreditHoldV2.created_at < cursor_dt,
                and_(CreditHoldV2.created_at == cursor_dt, CreditHoldV2.hold_id < cursor_id),
            )
        )

    rows = session.exec(q.order_by(CreditHoldV2.created_at.desc(), CreditHoldV2.hold_id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "hold_id": r.hold_id,
            "user_id": r.user_id,
            "request_id": r.request_id,
            "attempt_id": r.attempt_id,
            "idempotency_key": r.idempotency_key,
            "tier": r.tier,
            "action": r.action,
            "status": r.status,
            "reserved": float(r.amount_reserved),
            "settled": float(r.amount_settled),
            "released": float(r.amount_released),
            "created_at": r.created_at,
            "expires_at": r.expires_at,
        }
        for r in rows
    ]
    if items:
        next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].hold_id) if has_more and rows else None
        return CursorPage(items=items, next_cursor=next_cursor, limit=limit)

    # Legacy fallback for environments still writing CreditHold.
    legacy_q = select(CreditHold)
    if status:
        status_norm = status.lower()
        if status_norm == "active":
            legacy_q = legacy_q.where(CreditHold.status == "held")
        elif status_norm == "released":
            legacy_q = legacy_q.where(CreditHold.status.in_(["released", "released_void"]))
        elif status_norm == "settled":
            legacy_q = legacy_q.where(CreditHold.status == "finalized")
        else:
            legacy_q = legacy_q.where(CreditHold.status == status_norm)
    if user_id is not None:
        legacy_q = legacy_q.where(CreditHold.user_id == user_id)
    if date_from:
        legacy_q = legacy_q.where(CreditHold.created_at >= date_from)
    if date_to:
        legacy_q = legacy_q.where(CreditHold.created_at <= date_to)

    legacy_cursor_id_int: Optional[int] = None
    if cursor_id and cursor_id.startswith("legacy_hold_"):
        try:
            legacy_cursor_id_int = int(cursor_id.replace("legacy_hold_", ""))
        except Exception:
            legacy_cursor_id_int = None
    if cursor_dt and legacy_cursor_id_int is not None:
        legacy_q = legacy_q.where(
            or_(
                CreditHold.created_at < cursor_dt,
                and_(CreditHold.created_at == cursor_dt, CreditHold.id < legacy_cursor_id_int),
            )
        )

    legacy_rows = session.exec(
        legacy_q.order_by(CreditHold.created_at.desc(), CreditHold.id.desc()).limit(limit + 1)
    ).all()
    legacy_has_more = len(legacy_rows) > limit
    legacy_rows = legacy_rows[:limit]
    legacy_items = []
    for r in legacy_rows:
        meta = r.meta if isinstance(r.meta, dict) else {}
        status_value = (r.status or "").lower()
        is_finalized = status_value in {"finalized", "released"}
        is_void = status_value in {"released_void", "failed"}
        legacy_items.append(
            {
                "hold_id": f"legacy_hold_{r.id}",
                "user_id": r.user_id,
                "request_id": r.request_id,
                "attempt_id": str(meta.get("attempt_id") or ""),
                "idempotency_key": str(meta.get("idempotency_key") or ""),
                "tier": str(meta.get("tier") or ""),
                "action": str(meta.get("action") or "solve"),
                "status": "active" if status_value == "held" else ("released" if is_void else "settled"),
                "reserved": float(r.reserved_credits or 0),
                "settled": float(r.reserved_credits or 0) if is_finalized else 0.0,
                "released": float(r.reserved_credits or 0) if is_void else 0.0,
                "created_at": r.created_at,
                "expires_at": None,
            }
        )
    legacy_next_cursor = (
        _encode_cursor(legacy_rows[-1].created_at, f"legacy_hold_{legacy_rows[-1].id}")
        if legacy_has_more and legacy_rows
        else None
    )
    return CursorPage(items=legacy_items, next_cursor=legacy_next_cursor, limit=limit)


@router.get("/lots", response_model=CursorPage)
def admin_credits_lots(
    user_id: int = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    cursor_dt, cursor_id = _decode_cursor(cursor)
    q = select(CreditLotV2).where(CreditLotV2.user_id == user_id)
    if cursor_dt and cursor_id:
        q = q.where(
            or_(
                CreditLotV2.created_at < cursor_dt,
                and_(CreditLotV2.created_at == cursor_dt, CreditLotV2.lot_id < cursor_id),
            )
        )
    rows = session.exec(q.order_by(CreditLotV2.created_at.desc(), CreditLotV2.lot_id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        {
            "lot_id": r.lot_id,
            "user_id": r.user_id,
            "source": r.source,
            "credits_total": float(r.credits_total),
            "credits_remaining": float(r.credits_remaining),
            "expires_at": r.expires_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].lot_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=limit)


@router.post("/grant")
def admin_grant_credits(
    body: GrantCreditsBody,
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_roles(current_user, GRANT_ROLES, "Only superadmin/admin can grant credits")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    target = session.get(User, body.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if idempotency_key:
        existing = session.exec(
            select(CreditLotV2)
            .where(CreditLotV2.user_id == body.user_id)
            .where(CreditLotV2.source == f"manual:{idempotency_key}")
            .order_by(CreditLotV2.created_at.desc())
        ).first()
        if existing:
            return {
                "ok": True,
                "idempotent_replay": True,
                "lot_id": existing.lot_id,
                "user_id": body.user_id,
                "credits_total": float(existing.credits_total),
            }

    lot = CreditLotV2(
        user_id=body.user_id,
        source=f"manual:{idempotency_key}" if idempotency_key else "manual",
        credits_total=body.credits,
        credits_remaining=body.credits,
        expires_at=body.expires_at,
    )
    session.add(lot)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=current_user.id,
        action="CREATE",
        entity_type="CREDIT_LOT_V2",
        entity_id=lot.lot_id,
        before_json={"user_id": body.user_id},
        after_json={
            "lot_id": lot.lot_id,
            "credits_total": float(body.credits),
            "expires_at": str(body.expires_at) if body.expires_at else None,
        },
        reason=body.reason,
        idempotency_key=idempotency_key,
        request=request,
    )
    session.commit()

    return {
        "ok": True,
        "lot_id": lot.lot_id,
        "user_id": lot.user_id,
        "credits_total": float(lot.credits_total),
        "credits_remaining": float(lot.credits_remaining),
        "expires_at": lot.expires_at,
        "created_at": lot.created_at,
    }


@router.post("/holds/{hold_id}/release")
def admin_release_hold(
    hold_id: str,
    body: ReleaseHoldBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_roles(current_user, {"superadmin"}, "Only superadmin can release holds")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    hold = session.get(CreditHoldV2, hold_id)
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    if hold.status != "active":
        raise HTTPException(status_code=400, detail=f"Hold is already {hold.status}")

    credit_billing_service.release_hold_full(session=session, hold_id=hold_id)

    audit_log_service.log_action(
        session=session,
        admin_user_id=current_user.id,
        action="EXECUTE",
        entity_type="CREDIT_HOLD_V2",
        entity_id=hold_id,
        before_json={"status": "active"},
        after_json={"status": "released"},
        reason=body.reason,
        idempotency_key=None,
        request=request,
    )
    session.commit()
    return {"ok": True, "hold_id": hold_id, "status": "released"}


@router.get("/packs")
def admin_list_credit_packs(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    packs = session.exec(select(TopUpProduct).order_by(TopUpProduct.credits.asc())).all()
    maps = session.exec(select(StripePriceMap).where(StripePriceMap.kind == "TOPUP").where(StripePriceMap.active == True)).all()
    by_code = {m.internal_code: m for m in maps}
    rows = []
    for idx, p in enumerate(packs):
        m = by_code.get(p.code)
        meta = p.metadata_json or {}
        rows.append(
            {
                "pack_code": p.code,
                "credits": p.credits,
                "active": p.is_active,
                "sort_order": idx + 1,
                "label": str(meta.get("label") or ""),
                "display_name": p.name or p.code,
                "stripe_product_id": None,
                "stripe_price_id": m.stripe_price_id if m else None,
                "stripe_mapping_ok": bool(m and m.stripe_price_id),
                "updated_at": None,
            }
        )
    return {"items": rows}


@router.patch("/packs/{pack_code}")
def admin_patch_credit_pack(
    pack_code: str,
    body: PatchPackBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_roles(current_user, WRITE_PACK_ROLES, "Only superadmin/admin can modify packs")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    pack = session.exec(select(TopUpProduct).where(TopUpProduct.code == pack_code)).first()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    meta = dict(pack.metadata_json or {})
    before = {
        "active": pack.is_active,
        "label": str(meta.get("label") or ""),
        "display_name": pack.name,
        "credits": pack.credits,
        "price_usd": pack.price_usd,
    }
    if body.active is not None:
        pack.is_active = body.active
    if body.label is not None:
        meta["label"] = body.label
    if body.display_name is not None and body.display_name.strip():
        pack.name = body.display_name.strip()
    if body.sort_order is not None:
        meta["sort_order"] = int(body.sort_order)
    pack.metadata_json = meta
    session.add(pack)

    if body.stripe_price_id is not None:
        mapping = session.exec(
            select(StripePriceMap).where(StripePriceMap.kind == "TOPUP").where(StripePriceMap.internal_code == pack_code)
        ).first()
        if mapping:
            mapping.stripe_price_id = body.stripe_price_id.strip()
            mapping.active = True
            session.add(mapping)
        else:
            session.add(
                StripePriceMap(
                    kind="TOPUP",
                    internal_code=pack_code,
                    stripe_price_id=body.stripe_price_id.strip(),
                    currency="USD",
                    active=True,
                )
            )

    if body.stripe_product_id:
        meta = dict(pack.metadata_json or {})
        meta["stripe_product_id"] = body.stripe_product_id
        pack.metadata_json = meta
        session.add(pack)

    audit_log_service.log_action(
        session=session,
        admin_user_id=current_user.id,
        action="UPDATE",
        entity_type="TOPUP_PRODUCT",
        entity_id=pack_code,
        before_json=before,
        after_json={
            "active": pack.is_active,
            "label": str((pack.metadata_json or {}).get("label") or ""),
            "display_name": pack.name,
            "credits": pack.credits,
            "price_usd": pack.price_usd,
            "stripe_price_id": body.stripe_price_id,
            "stripe_product_id": body.stripe_product_id,
        },
        reason=body.reason,
        idempotency_key=None,
        request=request,
    )
    session.commit()
    return {"ok": True, "pack_code": pack_code}


@prompt_bindings_router.get("")
def admin_list_prompt_bindings(
    scope: str = Query(default="solve"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    q = select(PromptBinding)
    if scope.lower() == "solve":
        q = q.where(PromptBinding.mode == PromptModeEnum.SOLVE)
    rows = session.exec(q.order_by(PromptBinding.tier.asc(), PromptBinding.updated_at.desc())).all()
    def _val(obj: object, key: str, default=None):
        return getattr(obj, key, default)

    def _tier_key(raw: object) -> str:
        if raw is None:
            return ""
        value = getattr(raw, "value", raw)
        return str(value).strip().lower()

    def _cost_map(row: PromptBinding) -> dict:
        # Prefer dedicated columns per field; fall back to multipliers only for missing fields.
        multipliers = _val(row, "multipliers", {}) or {}
        credits = multipliers.get("credits") if isinstance(multipliers, dict) else {}
        credits = credits if isinstance(credits, dict) else {}
        solve = credits.get("solve") if isinstance(credits, dict) else {}
        solve = solve if isinstance(solve, dict) else {}
        tier_key = _tier_key(_val(row, "tier"))
        tier_cfg = solve.get(tier_key) if isinstance(solve, dict) else {}
        tier_cfg = tier_cfg if isinstance(tier_cfg, dict) else {}
        if not tier_cfg and tier_key == "short_steps":
            tier_cfg = solve.get("free") if isinstance(solve, dict) else {}
        if not tier_cfg and tier_key == "final":
            tier_cfg = solve.get("short") if isinstance(solve, dict) else {}
        verify_map = credits.get("verify") if isinstance(credits, dict) else {}
        verify_map = verify_map if isinstance(verify_map, dict) else {}
        attempt_map = credits.get("attempt_fee") if isinstance(credits, dict) else {}
        attempt_map = attempt_map if isinstance(attempt_map, dict) else {}
        fallback = {
            "solve_text_cost": float(tier_cfg.get("text") or 0),
            "solve_snap_image_cost": float(tier_cfg.get("snap_image") or 0),
            "solve_snap_pdf_cost": float(tier_cfg.get("snap_pdf") or 0),
            "solve_voice_cost": float(tier_cfg.get("voice") or 0),
            "verify_addon_cost": float(verify_map.get(tier_key) or verify_map.get("free" if tier_key == "short_steps" else ("short" if tier_key == "final" else tier_key)) or 0),
            "plot_addon_cost": float(credits.get("plot_trigger") or 0),
            "attempt_fee": float(attempt_map.get(tier_key) or attempt_map.get("free" if tier_key == "short_steps" else ("short" if tier_key == "final" else tier_key)) or 0),
        }

        return {
            "solve_text_cost": float(_val(row, "solve_text_cost")) if _val(row, "solve_text_cost") is not None else fallback["solve_text_cost"],
            "solve_snap_image_cost": float(_val(row, "solve_snap_image_cost")) if _val(row, "solve_snap_image_cost") is not None else fallback["solve_snap_image_cost"],
            "solve_snap_pdf_cost": float(_val(row, "solve_snap_pdf_cost")) if _val(row, "solve_snap_pdf_cost") is not None else fallback["solve_snap_pdf_cost"],
            "solve_voice_cost": float(_val(row, "solve_voice_cost")) if _val(row, "solve_voice_cost") is not None else fallback["solve_voice_cost"],
            "verify_addon_cost": float(_val(row, "verify_addon_cost")) if _val(row, "verify_addon_cost") is not None else fallback["verify_addon_cost"],
            "plot_addon_cost": float(_val(row, "plot_addon_cost")) if _val(row, "plot_addon_cost") is not None else fallback["plot_addon_cost"],
            "attempt_fee": float(_val(row, "attempt_fee")) if _val(row, "attempt_fee") is not None else fallback["attempt_fee"],
        }

    return {
        "items": [
            (lambda costs: {
                "id": r.id,
                "tier": str(getattr(r.tier, "value", r.tier)),
                "mode": str(getattr(r.mode, "value", r.mode)),
                "global_system_prompt_id": r.global_system_prompt_id,
                "developer_prompt_id": r.developer_prompt_id,
                "output_schema_id": r.output_schema_id,
                "openai_prompt_id": _val(r, "openai_prompt_id"),
                "openai_prompt_version": _val(r, "openai_prompt_version"),
                "openai_prompt_use_latest": bool(_val(r, "openai_prompt_use_latest", False)),
                "openai_prompt_variable_mapping": _val(r, "openai_prompt_variable_mapping"),
                "openai_prompt_cache_key_template": _val(r, "openai_prompt_cache_key_template"),
                "openai_prompt_cache_retention": _val(r, "openai_prompt_cache_retention"),
                "features": _val(r, "features", {}) or {},
                "multipliers": _val(r, "multipliers", {}) or {},
                "max_questions_allowed": _val(r, "max_questions_allowed"),
                "timeout_ms": _val(r, "timeout_ms"),
                "max_input_tokens": _val(r, "max_input_tokens"),
                "max_output_tokens": _val(r, "max_output_tokens"),
                "system_schema_budget_tokens": _val(r, "system_schema_budget_tokens"),
                "context_budget_tokens": _val(r, "context_budget_tokens"),
                "json_retry_max_output_tokens": _val(r, "json_retry_max_output_tokens"),
                "json_retry_max_attempts": _val(r, "json_retry_max_attempts"),
                "plot_points_cap": _val(r, "plot_points_cap"),
                "plot_traces_cap": _val(r, "plot_traces_cap"),
                "plot_annotations_cap": _val(r, "plot_annotations_cap"),
                "temperature": _val(r, "temperature"),
                "top_p": _val(r, "top_p"),
                "trim_strategy": str(getattr(_val(r, "trim_strategy"), "value", _val(r, "trim_strategy"))) if _val(r, "trim_strategy") is not None else None,
                "max_steps": _val(r, "max_steps"),
                "retry_cap_tokens": _val(r, "retry_cap_tokens"),
                "solve_text_cost": costs["solve_text_cost"],
                "solve_snap_image_cost": costs["solve_snap_image_cost"],
                "solve_snap_pdf_cost": costs["solve_snap_pdf_cost"],
                "solve_voice_cost": costs["solve_voice_cost"],
                "verify_addon_cost": costs["verify_addon_cost"],
                "plot_addon_cost": costs["plot_addon_cost"],
                "attempt_fee": costs["attempt_fee"],
                "is_active": r.is_active,
                "created_at": _val(r, "created_at"),
                "updated_at": r.updated_at,
                "updated_by": r.updated_by,
            })(_cost_map(r))
            for r in rows
        ]
    }


@prompt_bindings_router.patch("/{binding_id}")
def admin_patch_prompt_binding(
    binding_id: str,
    body: PatchPromptBindingBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    binding = session.get(PromptBinding, binding_id)
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")

    patch_data = body.model_dump(exclude_unset=True)
    changed_keys = {k for k in patch_data.keys() if k != "reason"}
    role = _role(current_user)
    if changed_keys and role not in {"superadmin", "admin"}:
        raise HTTPException(status_code=403, detail="Only admin/superadmin can modify prompt bindings")

    before = {
        "max_questions_allowed": getattr(binding, "max_questions_allowed", None),
        "timeout_ms": getattr(binding, "timeout_ms", None),
        "max_input_tokens": getattr(binding, "max_input_tokens", None),
        "max_output_tokens": getattr(binding, "max_output_tokens", None),
        "solve_text_cost": float(getattr(binding, "solve_text_cost", 0) or 0),
        "attempt_fee": float(getattr(binding, "attempt_fee", 0) or 0),
    }

    for key, value in patch_data.items():
        if key == "reason":
            continue
        if not hasattr(binding, key):
            continue
        setattr(binding, key, value)

    # Backfill missing dedicated pricing columns from multipliers after updates.
    # This prevents legacy "all-columns-required" fallback code paths from reverting to default multipliers.
    pricing_fields = {
        "solve_text_cost",
        "solve_snap_image_cost",
        "solve_snap_pdf_cost",
        "solve_voice_cost",
        "verify_addon_cost",
        "plot_addon_cost",
        "attempt_fee",
    }
    if changed_keys.intersection(pricing_fields):
        tier_raw = str(getattr(getattr(binding, "tier", None), "value", getattr(binding, "tier", ""))).strip().lower()
        multipliers = getattr(binding, "multipliers", {}) or {}
        credits = multipliers.get("credits") if isinstance(multipliers, dict) else {}
        credits = credits if isinstance(credits, dict) else {}
        solve = credits.get("solve") if isinstance(credits, dict) else {}
        solve = solve if isinstance(solve, dict) else {}
        tier_cfg = solve.get(tier_raw) if isinstance(solve, dict) else {}
        tier_cfg = tier_cfg if isinstance(tier_cfg, dict) else {}
        if not tier_cfg and tier_raw == "short_steps":
            tier_cfg = solve.get("free") if isinstance(solve, dict) else {}
        if not tier_cfg and tier_raw == "final":
            tier_cfg = solve.get("short") if isinstance(solve, dict) else {}
        verify_map = credits.get("verify") if isinstance(credits, dict) else {}
        verify_map = verify_map if isinstance(verify_map, dict) else {}
        attempt_map = credits.get("attempt_fee") if isinstance(credits, dict) else {}
        attempt_map = attempt_map if isinstance(attempt_map, dict) else {}
        alias_key = "free" if tier_raw == "short_steps" else ("short" if tier_raw == "final" else tier_raw)
        fallback = {
            "solve_text_cost": Decimal(str(tier_cfg.get("text") or 0)),
            "solve_snap_image_cost": Decimal(str(tier_cfg.get("snap_image") or 0)),
            "solve_snap_pdf_cost": Decimal(str(tier_cfg.get("snap_pdf") or 0)),
            "solve_voice_cost": Decimal(str(tier_cfg.get("voice") or 0)),
            "verify_addon_cost": Decimal(str(verify_map.get(tier_raw) or verify_map.get(alias_key) or 0)),
            "plot_addon_cost": Decimal(str(credits.get("plot_trigger") or 0)),
            "attempt_fee": Decimal(str(attempt_map.get(tier_raw) or attempt_map.get(alias_key) or 0)),
        }
        for field, value in fallback.items():
            if getattr(binding, field, None) is None:
                setattr(binding, field, value)

    binding.updated_at = datetime.utcnow()
    binding.updated_by = current_user.email
    session.add(binding)

    audit_log_service.log_action(
        session=session,
        admin_user_id=current_user.id,
        action="UPDATE",
        entity_type="PROMPT_BINDING",
        entity_id=binding.id,
        before_json=jsonable_encoder(before),
        after_json=jsonable_encoder({k: getattr(binding, k) for k in changed_keys if hasattr(binding, k)}),
        reason=body.reason,
        idempotency_key=None,
        request=request,
    )
    session.commit()
    applied_keys = sorted([k for k in changed_keys if hasattr(binding, k)])
    return {"ok": True, "binding_id": binding.id, "changed": applied_keys}


@router.get("/overview")
def admin_credits_overview(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    tier: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin_read(current_user)
    now = datetime.utcnow()
    one_day_ago = now - timedelta(days=1)
    from_dt = date_from or one_day_ago
    to_dt = date_to or now

    lots_q_v2 = select(func.coalesce(func.sum(CreditLotV2.credits_total), 0))
    lots_q_legacy = select(func.coalesce(func.sum(CreditLot.credits_total), 0))
    consumed_q_v2 = select(func.coalesce(func.sum(UsageLedgerV2.total_cost), 0))
    consumed_q_legacy = select(func.coalesce(func.sum(BillingLedger.credits_charged), 0)).where(
        BillingLedger.status.in_(["SETTLED", "CHARGED"])
    )
    holds_count_q = select(func.count(CreditHoldV2.hold_id)).where(CreditHoldV2.status == "active")
    holds_amount_q = select(
        func.coalesce(func.sum(CreditHoldV2.amount_reserved - CreditHoldV2.amount_settled - CreditHoldV2.amount_released), 0)
    ).where(CreditHoldV2.status == "active")
    legacy_holds_count_q = select(func.count(CreditHold.id)).where(CreditHold.status == "held")
    legacy_holds_amount_q = select(func.coalesce(func.sum(CreditHold.reserved_credits), 0)).where(CreditHold.status == "held")

    if tier:
        consumed_q_v2 = consumed_q_v2.where(UsageLedgerV2.tier == tier.upper())
        consumed_q_legacy = consumed_q_legacy.where(BillingLedger.tier == tier.upper())
        holds_count_q = holds_count_q.where(CreditHoldV2.tier == tier.upper())
        holds_amount_q = holds_amount_q.where(CreditHoldV2.tier == tier.upper())

    insufficient_count = session.exec(
        select(func.count(CreditHoldV2.hold_id))
        .where(CreditHoldV2.created_at >= from_dt)
        .where(CreditHoldV2.created_at <= to_dt)
        .where(CreditHoldV2.status == "released")
        .where(CreditHoldV2.amount_settled == 0)
    ).one()
    provider_failures = session.exec(
        select(func.count(CreditHoldV2.hold_id))
        .where(CreditHoldV2.created_at >= from_dt)
        .where(CreditHoldV2.created_at <= to_dt)
        .where(CreditHoldV2.status == "released")
        .where(CreditHoldV2.amount_settled == 0)
        .where(CreditHoldV2.amount_released == CreditHoldV2.amount_reserved)
    ).one()
    last_ledger_v2 = session.exec(select(UsageLedgerV2).order_by(UsageLedgerV2.created_at.desc())).first()
    last_ledger_legacy = session.exec(select(BillingLedger).order_by(BillingLedger.created_at.desc())).first()
    last_ledger_at = None
    if last_ledger_v2 and last_ledger_legacy:
        last_ledger_at = max(last_ledger_v2.created_at, last_ledger_legacy.created_at)
    elif last_ledger_v2:
        last_ledger_at = last_ledger_v2.created_at
    elif last_ledger_legacy:
        last_ledger_at = last_ledger_legacy.created_at

    return {
        "total_credits_issued": float(session.exec(lots_q_v2).one() or 0) + float(session.exec(lots_q_legacy).one() or 0),
        "total_credits_consumed": float(session.exec(consumed_q_v2).one() or 0) + float(session.exec(consumed_q_legacy).one() or 0),
        "active_holds_count": int(session.exec(holds_count_q).one() or 0) + int(session.exec(legacy_holds_count_q).one() or 0),
        "active_holds_reserved": float(session.exec(holds_amount_q).one() or 0) + float(session.exec(legacy_holds_amount_q).one() or 0),
        "insufficient_credits_count": int(insufficient_count),
        "provider_failures_count": int(provider_failures),
        "last_ledger_entry_at": last_ledger_at,
        "range": {"date_from": from_dt, "date_to": to_dt, "tier": tier},
    }
