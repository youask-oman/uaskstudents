from typing import Optional

from app.models import User


LEGACY_TIER_TO_PLAN_SLUG = {
    "free": "short_steps",
    "short_steps": "short_steps",
    "short": "final",
    "final": "final",
    "standard": "standard",
    "student_standard": "standard",
    "pro": "standard",
    "premium": "standard",
    "research": "research",
    "family": "family_standard",
    "family_standard": "family_standard",
    "enterprise": "research",
}


def normalize_tier_slug(tier: Optional[str]) -> str:
    slug = (tier or "short_steps").strip().lower()
    return LEGACY_TIER_TO_PLAN_SLUG.get(slug, slug or "short_steps")


def runtime_tier_from_plan_slug(plan_slug: Optional[str]) -> str:
    """
    Map persisted plan slugs to runtime tier keys used by solve/debug/cost UI.
    """
    slug = normalize_tier_slug(plan_slug)
    if slug == "research":
        return "RESEARCH"
    if slug in {"standard", "student_standard", "pro", "premium"}:
        return "STANDARD"
    if slug in {"final", "family_standard", "short"}:
        return "FINAL"
    return "SHORT_STEPS"


def get_user_effective_tier_slug(user: Optional[User]) -> str:
    if not user:
        return "short_steps"

    # Source of truth is the user tier marker, not legacy Plan rows.
    return normalize_tier_slug(getattr(user, "subscription_tier", None))


def is_paid_tier_slug(tier: Optional[str]) -> bool:
    return normalize_tier_slug(tier) != "short_steps"
