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
    CreditHoldAllocationV2,
    CreditHoldV2,
    CreditLotV2,
    PromptBinding,
    PromptModeEnum,
    PromptTierEnum,
    StripePriceMap,
    TopUpProduct,
    TrimStrategyEnum,
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


class CursorPage(BaseModel):
    items: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    limit: int


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
    if user_id is not None:
        q = q.where(UsageLedgerV2.user_id == user_id)
    if tier:
        q = q.where(UsageLedgerV2.tier == tier.upper())
    if action:
        q = q.where(UsageLedgerV2.action == action)
    if outcome:
        q = q.where(UsageLedgerV2.outcome == outcome)
    if date_from:
        q = q.where(UsageLedgerV2.created_at >= date_from)
    if date_to:
        q = q.where(UsageLedgerV2.created_at <= date_to)
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

    items = [
        {
            "ledger_id": r.ledger_id,
            "user_id": r.user_id,
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
            "outcome": r.outcome,
            "pricing_snapshot": r.pricing_snapshot,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].ledger_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=limit)


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
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].hold_id) if has_more and rows else None
    return CursorPage(items=items, next_cursor=next_cursor, limit=limit)


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
        # Prefer dedicated columns; fall back to multipliers JSON for compatibility.
        direct = {
            "solve_text_cost": _val(row, "solve_text_cost"),
            "solve_snap_image_cost": _val(row, "solve_snap_image_cost"),
            "solve_snap_pdf_cost": _val(row, "solve_snap_pdf_cost"),
            "solve_voice_cost": _val(row, "solve_voice_cost"),
            "verify_addon_cost": _val(row, "verify_addon_cost"),
            "plot_addon_cost": _val(row, "plot_addon_cost"),
            "attempt_fee": _val(row, "attempt_fee"),
        }
        if all(v is not None for v in direct.values()):
            return {k: float(v or 0) for k, v in direct.items()}

        multipliers = _val(row, "multipliers", {}) or {}
        credits = multipliers.get("credits") if isinstance(multipliers, dict) else {}
        credits = credits if isinstance(credits, dict) else {}
        solve = credits.get("solve") if isinstance(credits, dict) else {}
        solve = solve if isinstance(solve, dict) else {}
        tier_key = _tier_key(_val(row, "tier"))
        tier_cfg = solve.get(tier_key) if isinstance(solve, dict) else {}
        tier_cfg = tier_cfg if isinstance(tier_cfg, dict) else {}
        verify_map = credits.get("verify") if isinstance(credits, dict) else {}
        verify_map = verify_map if isinstance(verify_map, dict) else {}
        attempt_map = credits.get("attempt_fee") if isinstance(credits, dict) else {}
        attempt_map = attempt_map if isinstance(attempt_map, dict) else {}

        return {
            "solve_text_cost": float(tier_cfg.get("text") or 0),
            "solve_snap_image_cost": float(tier_cfg.get("snap_image") or 0),
            "solve_snap_pdf_cost": float(tier_cfg.get("snap_pdf") or 0),
            "solve_voice_cost": float(tier_cfg.get("voice") or 0),
            "verify_addon_cost": float(verify_map.get(tier_key) or 0),
            "plot_addon_cost": float(credits.get("plot_trigger") or 0),
            "attempt_fee": float(attempt_map.get(tier_key) or 0),
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

    changed_keys = {k for k, v in body.model_dump().items() if k != "reason" and v is not None}
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

    for key, value in body.model_dump().items():
        if key in {"reason"} or value is None:
            continue
        if not hasattr(binding, key):
            continue
        setattr(binding, key, value)
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

    lots_q = select(func.coalesce(func.sum(CreditLotV2.credits_total), 0))
    consumed_q = select(func.coalesce(func.sum(UsageLedgerV2.total_cost), 0))
    holds_count_q = select(func.count(CreditHoldV2.hold_id)).where(CreditHoldV2.status == "active")
    holds_amount_q = select(
        func.coalesce(func.sum(CreditHoldV2.amount_reserved - CreditHoldV2.amount_settled - CreditHoldV2.amount_released), 0)
    ).where(CreditHoldV2.status == "active")

    if tier:
        consumed_q = consumed_q.where(UsageLedgerV2.tier == tier.upper())
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
    last_ledger = session.exec(select(UsageLedgerV2).order_by(UsageLedgerV2.created_at.desc())).first()

    return {
        "total_credits_issued": float(session.exec(lots_q).one()),
        "total_credits_consumed": float(session.exec(consumed_q).one()),
        "active_holds_count": int(session.exec(holds_count_q).one()),
        "active_holds_reserved": float(session.exec(holds_amount_q).one()),
        "insufficient_credits_count": int(insufficient_count),
        "provider_failures_count": int(provider_failures),
        "last_ledger_entry_at": last_ledger.created_at if last_ledger else None,
        "range": {"date_from": from_dt, "date_to": to_dt, "tier": tier},
    }
