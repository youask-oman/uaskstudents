from typing import Optional

from sqlmodel import Session, select

from app.llm_profiles.profiles import PromptProfile, get_profile_free
from app.models import Plan, User
from app.services.prompt_registry_service import PromptRegistryError, prompt_registry_service
from app.services.tier_utils import get_user_effective_tier_slug, normalize_tier_slug
from app.services.token_policy import get_token_policy
from app.utils.token_limits import get_effective_max_steps, get_effective_max_tokens


class ProfileResolutionError(Exception):
    """Raised when a profile cannot be resolved."""


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
            print("WARNING: No 'free' plan found in DB. Using hardcoded fallback.")
            return get_profile_free()

        policy = get_token_policy(session)
        max_tokens = get_effective_max_tokens(requested_mode, learning_mode, policy)
        max_steps = get_effective_max_steps(requested_mode, learning_mode, policy)

        try:
            system_prompt, schema_content, _ = prompt_registry_service.resolve_binding_payload(
                session=session,
                tier_slug=tier_slug,
                mode="solve",
            )
            return PromptProfile(
                tier=tier_slug,
                system_prompt_content=system_prompt,
                json_schema_content=schema_content if isinstance(schema_content, dict) else {},
                max_output_tokens=max_tokens,
                max_steps=max_steps,
                mode=requested_mode,
                allow_detailed=(requested_mode == "detailed"),
                allow_visuals_only_if_asked=(requested_mode == "minimal" and "free" in tier_slug),
            )
        except PromptRegistryError:
            # Hard fallback to FREE binding only; no legacy table dependency.
            try:
                system_prompt, schema_content, _ = prompt_registry_service.resolve_binding_payload(
                    session=session,
                    tier_slug="free",
                    mode="solve",
                )
                return PromptProfile(
                    tier="free",
                    system_prompt_content=system_prompt,
                    json_schema_content=schema_content if isinstance(schema_content, dict) else {},
                    max_output_tokens=max_tokens,
                    max_steps=max_steps,
                    mode=requested_mode,
                    allow_detailed=(requested_mode == "detailed"),
                    allow_visuals_only_if_asked=True,
                )
            except PromptRegistryError as e:
                if tier_slug != "free":
                    print(
                        f"WARNING: Missing prompt registry binding for tier={tier_slug}; using hardcoded free fallback. ({e})"
                    )
                return get_profile_free()
