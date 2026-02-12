from typing import Optional

from app.models import User


LEGACY_TIER_TO_PLAN_SLUG = {
    "free": "free",
    "short": "family_standard",
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
    slug = (tier or "free").strip().lower()
    return LEGACY_TIER_TO_PLAN_SLUG.get(slug, slug or "free")


def runtime_tier_from_plan_slug(plan_slug: Optional[str]) -> str:
    """
    Map persisted plan slugs to runtime tier keys used by solve/debug/cost UI.
    """
    slug = normalize_tier_slug(plan_slug)
    if slug == "research":
        return "RESEARCH"
    if slug in {"standard", "student_standard", "pro", "premium"}:
        return "STANDARD"
    if slug in {"family_standard", "short"}:
        return "SHORT"
    return "FREE"


def get_user_effective_tier_slug(user: Optional[User]) -> str:
    if not user:
        return "free"

    # Source of truth is the user tier marker, not legacy Plan rows.
    return normalize_tier_slug(getattr(user, "subscription_tier", None))


def is_paid_tier_slug(tier: Optional[str]) -> bool:
    return normalize_tier_slug(tier) != "free"
