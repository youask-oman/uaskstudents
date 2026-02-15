from __future__ import annotations

from typing import Literal, Optional, Tuple

from sqlmodel import Session, select

from app.models import PromptBinding, PromptModeEnum, PromptTierEnum
from app.schemas.pricing import PlanFeatures, PlanMultipliers

TierKey = Literal["free", "short", "standard", "research"]


def normalize_tier_key(raw_tier: Optional[str]) -> TierKey:
    value = (raw_tier or "").strip().lower()
    if value in {"three_step", "free"}:
        return "free"
    if value in {"short", "final"}:
        return "short"
    if value in {"research"}:
        return "research"
    if value in {"standard"}:
        return "standard"
    return "free"


def _tier_to_enum(tier_key: TierKey) -> PromptTierEnum:
    if tier_key == "free":
        return PromptTierEnum.FREE
    if tier_key == "short":
        return PromptTierEnum.SHORT
    if tier_key == "research":
        return PromptTierEnum.RESEARCH
    return PromptTierEnum.STANDARD


def get_active_solve_binding(session: Session, raw_tier: Optional[str]) -> Optional[PromptBinding]:
    tier_key = normalize_tier_key(raw_tier)
    tier = _tier_to_enum(tier_key)
    try:
        return session.exec(
            select(PromptBinding)
            .where(PromptBinding.tier == tier)
            .where(PromptBinding.mode == PromptModeEnum.SOLVE)
            .where(PromptBinding.is_active == True)
            .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
        ).first()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
        return None


def resolve_binding_pricing(session: Session, raw_tier: Optional[str]) -> Tuple[PlanFeatures, PlanMultipliers, Optional[PromptBinding]]:
    binding = get_active_solve_binding(session, raw_tier)
    try:
        features = PlanFeatures(**((binding.features if binding else None) or {}))
        multipliers = PlanMultipliers(**((binding.multipliers if binding else None) or {}))
        return features, multipliers, binding
    except Exception:
        # Keep the service resilient when DB JSON payloads are partially invalid.
        return PlanFeatures(), PlanMultipliers(), binding


def resolve_solve_base_cost(
    session: Session,
    raw_tier: Optional[str],
    source_type: Literal["text", "snap_image", "snap_pdf", "voice"],
) -> float:
    tier_key = normalize_tier_key(raw_tier)
    _, multipliers, _ = resolve_binding_pricing(session, raw_tier)
    tier_config = getattr(multipliers.credits.solve, tier_key, None)
    if tier_config is None:
        raise ValueError(f"Missing tier pricing configuration for tier={tier_key}")

    if source_type == "snap_image":
        return float(tier_config.snap_image)
    if source_type == "snap_pdf":
        return float(tier_config.snap_pdf)
    if source_type == "voice":
        return float(tier_config.voice)
    return float(tier_config.text)
