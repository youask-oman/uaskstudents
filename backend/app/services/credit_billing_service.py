from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlmodel import Session, select

from app.models import (
    CreditHoldAllocationV2,
    CreditHoldV2,
    CreditLotV2,
    PromptBinding,
    PromptModeEnum,
    PromptTierEnum,
    UsageLedgerV2,
)


DECIMAL_ZERO = Decimal("0")
HOLD_TTL_MINUTES = 10


class CreditBillingError(Exception):
    def __init__(self, message: str, code: str = "billing_error", status_code: int = 400, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}


@dataclass
class ItemCost:
    question_id: str
    question_index: int
    base_cost: Decimal
    addons_cost: Decimal
    attempt_fee: Decimal
    total_reserved: Decimal


@dataclass
class ReserveResult:
    hold_id: str
    idempotency_key: str
    amount_reserved: Decimal
    item_costs: List[ItemCost]
    pricing_snapshot: Dict[str, Any]
    reused: bool = False
    hold_status: Optional[str] = None


def _normalize_tier(tier: str) -> str:
    raw = str(tier or "").strip().upper()
    if raw in {"FINAL", "SHORT"}:
        return "SHORT"
    if raw == "FREE":
        return "FREE"
    if raw == "STANDARD":
        return "STANDARD"
    if raw == "RESEARCH":
        return "RESEARCH"
    return "FREE"


def _pricing_key_for_tier(tier: str) -> str:
    if tier == "SHORT":
        return "short"
    return tier.lower()


def _stable_idempotency_key(
    user_id: int,
    tier: str,
    mode: str,
    modality: str,
    verify_requested: bool,
    plot_requested: bool,
    questions_json: List[Dict[str, Any]],
    provided: Optional[str],
) -> str:
    if provided and provided.strip():
        return provided.strip()
    payload = {
        "user_id": user_id,
        "tier": tier,
        "mode": mode,
        "modality": modality,
        "verify_requested": verify_requested,
        "plot_requested": plot_requested,
        "questions": questions_json,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"solve_batch:{digest}"


def _select_binding(session: Session, tier: str) -> PromptBinding:
    tier_enum = PromptTierEnum(tier)
    row = session.exec(
        select(PromptBinding)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
        .where(PromptBinding.tier == tier_enum)
        .where(PromptBinding.is_active == True)
        .order_by(PromptBinding.updated_at.desc())
    ).first()
    if not row:
        raise CreditBillingError(
            f"Missing active prompt binding for tier={tier}",
            code="prompt_binding_missing",
            status_code=500,
        )
    return row


def _costs_from_binding(binding: PromptBinding, tier: str) -> Dict[str, Decimal]:
    # Prefer dedicated columns. Fall back to multipliers for backward compatibility.
    if (
        binding.solve_text_cost is not None
        and binding.solve_snap_image_cost is not None
        and binding.solve_snap_pdf_cost is not None
        and binding.solve_voice_cost is not None
        and binding.verify_addon_cost is not None
        and binding.plot_addon_cost is not None
        and binding.attempt_fee is not None
    ):
        return {
            "text": Decimal(str(binding.solve_text_cost)),
            "snap_image": Decimal(str(binding.solve_snap_image_cost)),
            "snap_pdf": Decimal(str(binding.solve_snap_pdf_cost)),
            "voice": Decimal(str(binding.solve_voice_cost)),
            "verify_addon": Decimal(str(binding.verify_addon_cost)),
            "plot_addon": Decimal(str(binding.plot_addon_cost)),
            "attempt_fee": Decimal(str(binding.attempt_fee)),
        }

    mults = binding.multipliers or {}
    credits = mults.get("credits") or {}
    solve = credits.get("solve") or {}
    key = _pricing_key_for_tier(tier)
    tier_cfg = solve.get(key) or {}
    verify_map = credits.get("verify") or {}
    attempt_map = credits.get("attempt_fee") or {}
    return {
        "text": Decimal(str(tier_cfg.get("text") or 0)),
        "snap_image": Decimal(str(tier_cfg.get("snap_image") or 0)),
        "snap_pdf": Decimal(str(tier_cfg.get("snap_pdf") or 0)),
        "voice": Decimal(str(tier_cfg.get("voice") or 0)),
        "verify_addon": Decimal(str(verify_map.get(key) or 0)),
        "plot_addon": Decimal(str(credits.get("plot_trigger") or 0)),
        "attempt_fee": Decimal(str(attempt_map.get(key) or 0)),
    }


def _modality_to_base_key(modality: str) -> str:
    m = (modality or "").strip().lower()
    if m in {"snap_image", "ocr_image", "image"}:
        return "snap_image"
    if m in {"snap_pdf", "ocr_pdf", "pdf"}:
        return "snap_pdf"
    if m in {"voice"}:
        return "voice"
    return "text"


def _build_item_costs(
    questions_json: List[Dict[str, Any]],
    costs: Dict[str, Decimal],
    modality: str,
    verify_requested: bool,
    plot_requested: bool,
    include_attempt_fee: bool,
) -> List[ItemCost]:
    base_key = _modality_to_base_key(modality)
    base_cost = costs[base_key]
    addons = DECIMAL_ZERO
    if verify_requested:
        addons += costs["verify_addon"]
    if plot_requested:
        addons += costs["plot_addon"]
    attempt_fee = costs["attempt_fee"] if include_attempt_fee else DECIMAL_ZERO

    rows: List[ItemCost] = []
    for idx, q in enumerate(questions_json, start=1):
        qid = str(q.get("question_id") or f"q{idx}")
        total = base_cost + addons + attempt_fee
        rows.append(
            ItemCost(
                question_id=qid,
                question_index=idx,
                base_cost=base_cost,
                addons_cost=addons,
                attempt_fee=attempt_fee,
                total_reserved=total,
            )
        )
    return rows


class CreditBillingService:
    def reserve_for_batch_solve(
        self,
        *,
        session: Session,
        user_id: int,
        tier: str,
        mode: str,
        modality: str,
        verify_requested: bool,
        plot_requested: bool,
        questions_json: List[Dict[str, Any]],
        request_id: str,
        attempt_id: str,
        idempotency_key: Optional[str],
    ) -> ReserveResult:
        norm_tier = _normalize_tier(tier)
        binding = _select_binding(session, norm_tier)
        max_q = int(binding.max_questions_allowed or 0)
        if max_q < 1:
            raise CreditBillingError("Binding is missing max_questions_allowed", code="binding_invalid", status_code=500)
        if len(questions_json) > max_q:
            raise CreditBillingError(
                f"Batch exceeds tier max questions: max={max_q}, got={len(questions_json)}",
                code="batch_limit_exceeded",
                status_code=400,
                details={"max_questions_allowed": max_q, "count": len(questions_json)},
            )

        idem_key = _stable_idempotency_key(
            user_id=user_id,
            tier=norm_tier,
            mode=mode,
            modality=modality,
            verify_requested=verify_requested,
            plot_requested=plot_requested,
            questions_json=questions_json,
            provided=idempotency_key,
        )

        existing = session.exec(
            select(CreditHoldV2)
            .where(CreditHoldV2.user_id == user_id)
            .where(CreditHoldV2.idempotency_key == idem_key)
            .order_by(CreditHoldV2.created_at.desc())
        ).first()
        if existing and existing.status in {"active", "settled"}:
            item_costs = _build_item_costs(
                questions_json=questions_json,
                costs=_costs_from_binding(binding, norm_tier),
                modality=modality,
                verify_requested=verify_requested,
                plot_requested=plot_requested,
                include_attempt_fee=True,
            )
            return ReserveResult(
                hold_id=existing.hold_id,
                idempotency_key=idem_key,
                amount_reserved=Decimal(str(existing.amount_reserved)),
                item_costs=item_costs,
                pricing_snapshot=self._pricing_snapshot(binding, norm_tier, modality, verify_requested, plot_requested),
                reused=True,
                hold_status=existing.status,
            )

        costs = _costs_from_binding(binding, norm_tier)
        item_costs = _build_item_costs(
            questions_json=questions_json,
            costs=costs,
            modality=modality,
            verify_requested=verify_requested,
            plot_requested=plot_requested,
            include_attempt_fee=True,
        )
        amount_reserved = sum((row.total_reserved for row in item_costs), DECIMAL_ZERO)
        if amount_reserved <= DECIMAL_ZERO:
            raise CreditBillingError("Computed reserved amount must be > 0", code="invalid_pricing", status_code=500)

        lots = session.exec(
            select(CreditLotV2)
            .where(CreditLotV2.user_id == user_id)
            .where(CreditLotV2.credits_remaining > 0)
            .order_by(CreditLotV2.expires_at.asc().nullslast(), CreditLotV2.created_at.asc())
            .with_for_update(skip_locked=True)
        ).all()

        remaining = amount_reserved
        allocations: List[Tuple[CreditLotV2, Decimal]] = []
        for lot in lots:
            if remaining <= DECIMAL_ZERO:
                break
            available = Decimal(str(lot.credits_remaining))
            if available <= DECIMAL_ZERO:
                continue
            take = available if available <= remaining else remaining
            lot.credits_remaining = available - take
            session.add(lot)
            allocations.append((lot, take))
            remaining -= take

        if remaining > DECIMAL_ZERO:
            raise CreditBillingError(
                "Insufficient credits for reserve",
                code="insufficient_credits",
                status_code=402,
                details={"required": float(amount_reserved), "missing": float(remaining)},
            )

        hold = CreditHoldV2(
            hold_id=str(uuid4()),
            user_id=user_id,
            request_id=request_id,
            attempt_id=attempt_id,
            idempotency_key=idem_key,
            tier=norm_tier,
            action="solve_batch",
            amount_reserved=amount_reserved,
            amount_settled=DECIMAL_ZERO,
            amount_released=DECIMAL_ZERO,
            status="active",
            expires_at=datetime.utcnow() + timedelta(minutes=HOLD_TTL_MINUTES),
        )
        session.add(hold)
        session.flush()

        for lot, amount in allocations:
            session.add(
                CreditHoldAllocationV2(
                    hold_id=hold.hold_id,
                    lot_id=lot.lot_id,
                    amount=amount,
                )
            )

        pricing_snapshot = self._pricing_snapshot(binding, norm_tier, modality, verify_requested, plot_requested)
        return ReserveResult(
            hold_id=hold.hold_id,
            idempotency_key=idem_key,
            amount_reserved=amount_reserved,
            item_costs=item_costs,
            pricing_snapshot=pricing_snapshot,
            reused=False,
            hold_status=hold.status,
        )

    def settle_batch_hold(
        self,
        *,
        session: Session,
        hold_id: str,
        request_id: str,
        attempt_id: str,
        idempotency_key: str,
        item_costs: List[ItemCost],
        payload_items: List[Dict[str, Any]],
        pricing_snapshot: Dict[str, Any],
        provider_failed: bool = False,
    ) -> Dict[str, Any]:
        hold = session.exec(
            select(CreditHoldV2)
            .where(CreditHoldV2.hold_id == hold_id)
            .with_for_update()
        ).first()
        if not hold:
            raise CreditBillingError("Hold not found", code="hold_not_found", status_code=500)
        if hold.status != "active":
            return {
                "hold_id": hold.hold_id,
                "amount_reserved": float(hold.amount_reserved),
                "amount_settled": float(hold.amount_settled),
                "amount_released": float(hold.amount_released),
                "status": hold.status,
            }

        costs_by_qid = {row.question_id: row for row in item_costs}
        total_settled = DECIMAL_ZERO

        for idx, item in enumerate(payload_items, start=1):
            qid = str(item.get("question_id") or f"q{idx}")
            row = costs_by_qid.get(qid)
            if row is None:
                row = item_costs[idx - 1] if idx - 1 < len(item_costs) else item_costs[-1]

            refusal = bool(((item.get("refusal") or {}) if isinstance(item.get("refusal"), dict) else {}).get("is_refusal"))
            if provider_failed:
                charge = DECIMAL_ZERO
                outcome = "error"
            elif refusal:
                charge = row.attempt_fee
                outcome = "refusal"
            else:
                charge = row.base_cost + row.addons_cost + row.attempt_fee
                outcome = "success"

            total_settled += charge
            session.add(
                UsageLedgerV2(
                    ledger_id=str(uuid4()),
                    user_id=hold.user_id,
                    hold_id=hold.hold_id,
                    request_id=request_id,
                    attempt_id=attempt_id,
                    idempotency_key=idempotency_key,
                    tier=hold.tier,
                    action=hold.action,
                    question_id=qid,
                    question_index=idx,
                    base_cost=row.base_cost,
                    addons_cost=row.addons_cost,
                    attempt_fee=row.attempt_fee,
                    total_cost=charge,
                    pricing_snapshot=pricing_snapshot,
                    outcome=outcome,
                )
            )

        reserved = Decimal(str(hold.amount_reserved))
        release_amount = reserved - total_settled
        if release_amount < DECIMAL_ZERO:
            release_amount = DECIMAL_ZERO

        if release_amount > DECIMAL_ZERO:
            self._release_to_lots(session=session, hold_id=hold.hold_id, release_amount=release_amount)

        hold.amount_settled = total_settled
        hold.amount_released = release_amount
        hold.status = "settled"
        session.add(hold)

        return {
            "hold_id": hold.hold_id,
            "amount_reserved": float(reserved),
            "amount_settled": float(total_settled),
            "amount_released": float(release_amount),
            "status": hold.status,
        }

    def release_hold_full(self, *, session: Session, hold_id: str) -> None:
        hold = session.exec(select(CreditHoldV2).where(CreditHoldV2.hold_id == hold_id).with_for_update()).first()
        if not hold or hold.status != "active":
            return
        amount = Decimal(str(hold.amount_reserved))
        if amount > DECIMAL_ZERO:
            self._release_to_lots(session=session, hold_id=hold.hold_id, release_amount=amount)
        hold.amount_settled = DECIMAL_ZERO
        hold.amount_released = amount
        hold.status = "released"
        session.add(hold)

    def _release_to_lots(self, *, session: Session, hold_id: str, release_amount: Decimal) -> None:
        allocations = session.exec(
            select(CreditHoldAllocationV2)
            .where(CreditHoldAllocationV2.hold_id == hold_id)
            .order_by(CreditHoldAllocationV2.lot_id.asc())
            .with_for_update()
        ).all()
        remaining = release_amount
        for alloc in allocations:
            if remaining <= DECIMAL_ZERO:
                break
            lot = session.exec(select(CreditLotV2).where(CreditLotV2.lot_id == alloc.lot_id).with_for_update()).first()
            if not lot:
                continue
            alloc_amount = Decimal(str(alloc.amount))
            refund = alloc_amount if alloc_amount <= remaining else remaining
            lot.credits_remaining = Decimal(str(lot.credits_remaining)) + refund
            session.add(lot)
            remaining -= refund

    def _pricing_snapshot(
        self,
        binding: PromptBinding,
        tier: str,
        modality: str,
        verify_requested: bool,
        plot_requested: bool,
    ) -> Dict[str, Any]:
        costs = _costs_from_binding(binding, tier)
        return {
            "binding_id": binding.id,
            "tier": tier,
            "mode": "SOLVE",
            "modality": modality,
            "verify_requested": verify_requested,
            "plot_requested": plot_requested,
            "costs": {
                "solve_text_cost": float(costs["text"]),
                "solve_snap_image_cost": float(costs["snap_image"]),
                "solve_snap_pdf_cost": float(costs["snap_pdf"]),
                "solve_voice_cost": float(costs["voice"]),
                "verify_addon_cost": float(costs["verify_addon"]),
                "plot_addon_cost": float(costs["plot_addon"]),
                "attempt_fee": float(costs["attempt_fee"]),
            },
        }


credit_billing_service = CreditBillingService()
