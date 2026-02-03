from typing import Optional

from sqlmodel import Session, select

from app.llm_profiles.profiles import PromptProfile
from app.models import Plan, User
from app.services.tier_utils import get_user_effective_tier_slug, normalize_tier_slug
from app.services.token_policy import get_token_policy
from app.utils.token_limits import get_effective_max_steps, get_effective_max_tokens
from app.prompts.db_loader import PromptBindingLookupError, load_prompt_bundle


class ProfileResolutionError(Exception):
    """Raised when a profile cannot be resolved."""
    def __init__(self, message: str, code: str = "PROFILE_RESOLUTION_FAILED", details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ProfileResolver:
    """
    Resolves the appropriate LLM PromptProfile for a given user and context.
    Source of truth: prompt registry bindings + prompt/templates + json_schemas.
    """

    @staticmethod
    def resolve_profile(
        session: Session,
        user: Optional[User],
        requested_mode: str = "minimal",  # "minimal" or "detailed"
        learning_mode: str = "solve",  # "solve" or "study"
        force_tier: Optional[str] = None,
        mode_family: str = "SOLVE",
        provider: str = "ollama",
    ) -> PromptProfile:
        plan = None
        tier_slug = "free"

        if force_tier:
            force_slug = normalize_tier_slug(force_tier)
            plan = session.exec(select(Plan).where(Plan.slug == force_slug)).first()
            tier_slug = plan.slug if plan else force_slug
        elif user and user.subscription and user.subscription.status == "active":
            plan = user.subscription.plan
            tier_slug = plan.slug if plan else "free"
        else:
            tier_slug = get_user_effective_tier_slug(user)

        if not plan:
            plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
            tier_slug = "free"

        if not plan:
            raise ProfileResolutionError("No plan found for profile resolution.")

        policy = get_token_policy(session)
        max_tokens = get_effective_max_tokens(requested_mode, learning_mode, policy)
        max_steps = get_effective_max_steps(requested_mode, learning_mode, policy)

        try:
            bundle = load_prompt_bundle(
                tier=tier_slug,
                mode=mode_family,
                session=session,
                provider=provider,
            )
        except PromptBindingLookupError as e:
            raise ProfileResolutionError(
                f"Prompt binding lookup failed: {e}",
                code=getattr(e, "code", "PROMPT_BINDING_LOOKUP_FAILED"),
                details=getattr(e, "details", {}),
            ) from e

        return PromptProfile(
            tier=tier_slug,
            system_prompt_content=bundle["system_prompt"],
            developer_prompt_content=bundle["developer_prompt"],
            json_schema_content=bundle["schema"] if isinstance(bundle["schema"], dict) else {},
            max_output_tokens=max_tokens,
            max_steps=max_steps,
            mode=requested_mode,
            allow_detailed=(requested_mode == "detailed"),
            allow_visuals_only_if_asked=(requested_mode == "minimal" and "free" in tier_slug),
            prompt_binding_meta=bundle.get("meta"),
        )
