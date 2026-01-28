from typing import Optional
from sqlmodel import Session, select
from app.models import User, Plan, PlanPromptLink, PromptAsset, Subscription
from app.llm_profiles.asset_loader import AssetLoader
from app.llm_profiles.profiles import PromptProfile, get_profile_free, get_prompt_profile
from app.services.token_policy import get_token_policy
from app.utils.token_limits import get_effective_max_tokens, get_effective_max_steps

class ProfileResolutionError(Exception):
    """Raised when a profile cannot be resolved (e.g. missing links)."""
    pass

class ProfileResolver:
    """
    Resolves the appropriate LLM PromptProfile for a given user and context.
    Uses Database-driven PlanPromptLinks.
    """
    
    @staticmethod
    def resolve_profile(
        session: Session,
        user: Optional[User],
        requested_mode: str = "minimal",  # "minimal" or "detailed"
        learning_mode: str = "solve",     # "solve" or "study"
        force_tier: Optional[str] = None
    ) -> PromptProfile:
        
        # 1. Determine Plan
        plan = None
        tier_slug = "free"
        
        if force_tier:
             plan = session.exec(select(Plan).where(Plan.slug == force_tier)).first()
             if plan:
                 tier_slug = plan.slug
        elif user and user.subscription and user.subscription.status == "active":
             plan = user.subscription.plan
             if plan:
                 tier_slug = plan.slug
        
        # If no plan found (or user is None/Free), try to get the default Free plan object
        if not plan:
            plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
            tier_slug = "free"

        if not plan:
            # Fallback if DB is completely broken/empty?
            # Use the hardcoded free profile from profiles.py as emergency fallback
            print("WARNING: No 'free' plan found in DB. Using hardcoded fallback.")
            return get_profile_free()

        # 2. Determine Effective Mode
        effective_mode = requested_mode
        
        # 3. Fetch Link
        # Optimization: We could join, but simple select is fine.
        link = session.exec(
            select(PlanPromptLink)
            .where(PlanPromptLink.plan_id == plan.id)
            .where(PlanPromptLink.mode == effective_mode)
        ).first()
        
        # DOWNGRADE LOGIC REMOVED to allow valid fallback.
        # Previously we forced minimal if detailed link was missing.
        # Now we proceed to _fallback_profile which can find shared defaults.
            
        if not link:
            fallback_profile = ProfileResolver._fallback_profile(session, tier_slug, effective_mode)
            if fallback_profile:
                return fallback_profile
            if tier_slug == "free":
                return get_profile_free()
            print(f"WARNING: Missing prompt links/assets for {tier_slug}. Using free fallback.")
            return get_profile_free()

        # 4. Load Assets
        try:
            sys_asset = session.get(PromptAsset, link.system_prompt_asset_id)
            if not sys_asset:
                raise ProfileResolutionError(f"System prompt asset {link.system_prompt_asset_id} missing.")
            
            schema_asset = session.get(PromptAsset, link.schema_prompt_asset_id)
            if not schema_asset:
                raise ProfileResolutionError(f"Schema prompt asset {link.schema_prompt_asset_id} missing.")
                
            system_content = AssetLoader.get_asset_content(sys_asset)
            schema_content = AssetLoader.get_asset_content(schema_asset)
            
        except Exception as e:
            raise ProfileResolutionError(f"Failed to load assets: {e}")

        # 5. Construct Profile
        policy = get_token_policy(session)
        max_tokens = get_effective_max_tokens(effective_mode, learning_mode, policy)
        max_steps = get_effective_max_steps(effective_mode, learning_mode, policy)
            
        # Optional: Plan level override for max_tokens ONLY if it is stricter
        if plan.features and "max_tokens" in plan.features:
            plan_max = int(plan.features["max_tokens"])
            if plan_max < max_tokens:
                max_tokens = plan_max

        return PromptProfile(
            tier=tier_slug,
            system_prompt_content=system_content if isinstance(system_content, str) else str(system_content),
            json_schema_content=schema_content if isinstance(schema_content, dict) else {},
            system_asset_path=sys_asset.path if sys_asset else None,
            schema_asset_path=schema_asset.path if schema_asset else None,
            system_asset_key=sys_asset.key if sys_asset else None,
            schema_asset_key=schema_asset.key if schema_asset else None,
            max_output_tokens=max_tokens,
            max_steps=max_steps,
            mode=effective_mode,
            allow_detailed=(effective_mode == "detailed"),
            allow_visuals_only_if_asked=(effective_mode == "minimal" and "free" in tier_slug)
        )

    @staticmethod
    def _fallback_profile(session: Session, tier_slug: str, effective_mode: str) -> Optional[PromptProfile]:
        # Fallback to shared assets (hardcoded keys point to DB entries)
        key_map = {
            "minimal": ("shared:minimal_system", "shared:minimal_schema"),
            "detailed": ("shared:detailed_system", "shared:canonical_schema"),
        }
        system_key, schema_key = key_map.get(effective_mode, key_map["minimal"])
        tier_for_profile = "standard" if ("standard" in tier_slug or "family" in tier_slug) else tier_slug
        profile_defaults = get_prompt_profile(tier_for_profile)

        # Look up assets by Key
        sys_asset = session.exec(select(PromptAsset).where(PromptAsset.key == system_key)).first()
        schema_asset = session.exec(select(PromptAsset).where(PromptAsset.key == schema_key)).first()
        
        if not sys_asset or not schema_asset:
            return None
            
        try:
            system_content = AssetLoader.get_asset_content(sys_asset)
            schema_content = AssetLoader.get_asset_content(schema_asset)
        except Exception:
            return None

        # Return profile using dynamic limits from SystemConfig
        policy = get_token_policy(session)
        max_tokens = get_effective_max_tokens(effective_mode, "solve", policy) # Default to 'solve' for fallback
        max_steps = get_effective_max_steps(effective_mode, "solve", policy)

        return PromptProfile(
            tier=tier_slug,
            system_prompt_content=system_content if isinstance(system_content, str) else str(system_content),
            json_schema_content=schema_content if isinstance(schema_content, dict) else {},
            system_asset_path=sys_asset.path if sys_asset else None,
            schema_asset_path=schema_asset.path if schema_asset else None,
            system_asset_key=sys_asset.key if sys_asset else None,
            schema_asset_key=schema_asset.key if schema_asset else None,
            max_output_tokens=max_tokens,
            max_steps=max_steps,
            mode=effective_mode,
            allow_detailed=(effective_mode == "detailed"),
            allow_visuals_only_if_asked=profile_defaults.allow_visuals_only_if_asked,
            cost_multiplier=profile_defaults.cost_multiplier
        )
