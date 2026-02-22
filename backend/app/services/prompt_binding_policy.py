from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.models import PromptTierEnum, TrimStrategyEnum


# Optional allowlists. Keep empty to enforce DB-driven bindings only.
ALLOWED_PROMPT_IDS: List[str] = []

# Optional allowlists. Keep empty to enforce DB-driven bindings only.
ALLOWED_SCHEMA_IDS: List[str] = []

ALLOWED_SOLVE_TIERS: List[PromptTierEnum] = [
    PromptTierEnum.FINAL,
    PromptTierEnum.SHORT_STEPS,
    PromptTierEnum.STANDARD,
    PromptTierEnum.RESEARCH,
]


@dataclass(frozen=True)
class SolveTierPolicy:
    prompt_tier: PromptTierEnum
    external_tier: str
    max_questions: int
    allow_research: bool
    solve_cost_text: int
    solve_cost_snap_image: int
    solve_cost_snap_pdf: int
    solve_cost_voice: int
    verify_cost: int


SOLVE_TIER_POLICY: Dict[str, SolveTierPolicy] = {
    "FINAL": SolveTierPolicy(
        prompt_tier=PromptTierEnum.FINAL,
        external_tier="FINAL",
        max_questions=15,
        allow_research=False,
        solve_cost_text=1,
        solve_cost_snap_image=2,
        solve_cost_snap_pdf=3,
        solve_cost_voice=2,
        verify_cost=1,
    ),
    "SHORT_STEPS": SolveTierPolicy(
        prompt_tier=PromptTierEnum.SHORT_STEPS,
        external_tier="SHORT_STEPS",
        max_questions=5,
        allow_research=False,
        solve_cost_text=1,
        solve_cost_snap_image=2,
        solve_cost_snap_pdf=3,
        solve_cost_voice=2,
        verify_cost=1,
    ),
    "STANDARD": SolveTierPolicy(
        prompt_tier=PromptTierEnum.STANDARD,
        external_tier="STANDARD",
        max_questions=2,
        allow_research=False,
        solve_cost_text=2,
        solve_cost_snap_image=3,
        solve_cost_snap_pdf=4,
        solve_cost_voice=3,
        verify_cost=1,
    ),
    "RESEARCH": SolveTierPolicy(
        prompt_tier=PromptTierEnum.RESEARCH,
        external_tier="RESEARCH",
        max_questions=1,
        allow_research=True,
        solve_cost_text=4,
        solve_cost_snap_image=5,
        solve_cost_snap_pdf=6,
        solve_cost_voice=5,
        verify_cost=2,
    ),
}

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_TRIM_STRATEGY = TrimStrategyEnum.TRIM_CONTEXT_FIRST


def normalize_external_tier(raw_tier: str | None) -> str:
    value = (raw_tier or "").strip().upper()
    if value in {"FINAL", "SHORT"}:
        return "FINAL"
    if value in {"SHORT_STEPS", "FREE", "THREE_STEP"}:
        return "SHORT_STEPS"
    if value in {"STANDARD", "RESEARCH"}:
        return value
    return "SHORT_STEPS"


def build_features(allow_research: bool) -> dict:
    return {
        "model": DEFAULT_MODEL,
        "allow_research": allow_research,
        "allow_verify": True,
        "allow_plot": True,
        "daily_credit_cap": None,
        "ocr_monthly_cap": None,
        "voice_monthly_cap": None,
        "generated_images_monthly_cap": None,
        "make_it_right_monthly_cap": None,
    }


def build_multipliers(policy: SolveTierPolicy) -> dict:
    solve_cost = {
        "text": policy.solve_cost_text,
        "snap_image": policy.solve_cost_snap_image,
        "snap_pdf": policy.solve_cost_snap_pdf,
        "voice": policy.solve_cost_voice,
    }
    return {
        "version": 1,
        "credits": {
            "solve": {
                "short_steps": {"text": 1, "snap_image": 2, "snap_pdf": 3, "voice": 2},
                "final": {"text": 1, "snap_image": 2, "snap_pdf": 3, "voice": 2},
                "standard": {"text": 2, "snap_image": 3, "snap_pdf": 4, "voice": 3},
                "research": {"text": 4, "snap_image": 5, "snap_pdf": 6, "voice": 5},
            },
            "verify": {
                "short_steps": 1,
                "final": 1,
                "standard": 1,
                "research": 2,
            },
            "plot_trigger": 0,
            "plot_spec": 1,
            "_active_tier_solve": solve_cost,
            "_active_tier_verify": policy.verify_cost,
        },
    }
