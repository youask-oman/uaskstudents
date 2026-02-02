from typing import Optional

from app.models import User


LEGACY_TIER_TO_PLAN_SLUG = {
    "free": "free",
    "standard": "student_standard",
    "student_standard": "student_standard",
    "pro": "student_standard",
    "premium": "student_standard",
    "research": "research",
    "family": "research",
    "enterprise": "research",
}


def normalize_tier_slug(tier: Optional[str]) -> str:
    slug = (tier or "free").strip().lower()
    return LEGACY_TIER_TO_PLAN_SLUG.get(slug, slug or "free")


def get_user_effective_tier_slug(user: Optional[User]) -> str:
    if not user:
        return "free"

    subscription = getattr(user, "subscription", None)
    if subscription and getattr(subscription, "status", None) == "active":
        plan = getattr(subscription, "plan", None)
        if plan and getattr(plan, "slug", None):
            return normalize_tier_slug(plan.slug)

    return normalize_tier_slug(getattr(user, "subscription_tier", None))


def is_paid_tier_slug(tier: Optional[str]) -> bool:
    return normalize_tier_slug(tier) != "free"
