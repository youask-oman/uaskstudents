from typing import Optional
from sqlmodel import Session, select
from app.models import User, Plan, PlanPromptLink, PromptAsset, Subscription
from app.llm_profiles.asset_loader import AssetLoader
from app.llm_profiles.profiles import PromptProfile, get_profile_free, get_prompt_profile

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
             # Admin override logic if needed, or mapping string to a plan?
             # For now, just logging or simplistic fallback if we supported dynamic tiers by string alone.
             # We really need a Plan object to get links.
             # If force_tier is passed, we might need to fetch that plan by slug.
             plan = session.exec(select(Plan).where(Plan.slug == force_tier)).first()
             if plan:
                 tier_slug = plan.slug
        elif user and user.subscription and user.subscription.status == "active":
             # Eager load plan if not present? Usually accessing user.subscription.plan triggers lazy load if session active.
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
        # - Free tier: force minimal unless specific override?
        # - Standard/Family: respect requested_mode
        # - Study mode: might force detailed if plan allows
        
        effective_mode = requested_mode
        
        # Logic: If requested 'detailed' but plan doesn't support it (e.g. Free), fallback to minimal?
        # Or check if link exists.
        
        # 3. Fetch Link
        # Optimization: We could join, but simple select is fine.
        link = session.exec(
            select(PlanPromptLink)
            .where(PlanPromptLink.plan_id == plan.id)
            .where(PlanPromptLink.mode == effective_mode)
        ).first()
        
        if not link and effective_mode == "detailed":
            # Fallback to minimal if detailed not configured
            effective_mode = "minimal"
            link = session.exec(
                select(PlanPromptLink)
                .where(PlanPromptLink.plan_id == plan.id)
                .where(PlanPromptLink.mode == "minimal")
            ).first()
            
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
        # We need to decide max output tokens and steps based on Plan or Mode.
        # Currently stored in python profile logic or plan features?
        # Plan model has `features` dict. We can store `max_tokens` there.
        # Or hardcode defaults based on mode/tier.
        
        # 5. Construct Profile - STRICT Token Caps for Minimal Mode
        max_tokens = 800
        max_steps = 5
        
        if "standard" in tier_slug or "family" in tier_slug:
            if effective_mode == "detailed":
                max_tokens = 12000
                max_steps = 25
            else:
                # STRICT CAP for Paid Minimal: 600 tokens
                # Enough for 2 steps + JSON overhead, but forces brevity.
                max_tokens = 600
                max_steps = 2
        elif effective_mode == "detailed":
            # Free tier detailed (fallback/mock)
            max_tokens = 2000
            max_steps = 8
        else:
            # Free Minimal: STRICT CAP 450 tokens
            max_tokens = 450
            max_steps = 2
            
        # Overrides from Plan features if present (handle with care)
        if plan.features and "max_tokens" in plan.features:
            plan_max = int(plan.features["max_tokens"])
            if effective_mode == "minimal":
                # Hard cap minimal mode to avoid runaway outputs.
                max_tokens = min(max_tokens, 700, plan_max)
            elif plan_max > max_tokens:
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
        key_map = {
            "minimal": ("shared:minimal_system", "shared:minimal_schema"),
            "detailed": ("shared:detailed_system", "shared:canonical_schema"),
        }
        system_key, schema_key = key_map.get(effective_mode, key_map["minimal"])
        tier_for_profile = "standard" if ("standard" in tier_slug or "family" in tier_slug) else tier_slug
        profile_defaults = get_prompt_profile(tier_for_profile)

        sys_asset = session.exec(select(PromptAsset).where(PromptAsset.key == system_key)).first()
        schema_asset = session.exec(select(PromptAsset).where(PromptAsset.key == schema_key)).first()
        if not sys_asset or not schema_asset:
            return None
        try:
            system_content = AssetLoader.get_asset_content(sys_asset)
            schema_content = AssetLoader.get_asset_content(schema_asset)
        except Exception:
            return None

        return PromptProfile(
            tier=tier_slug,
            system_prompt_content=system_content if isinstance(system_content, str) else str(system_content),
            json_schema_content=schema_content if isinstance(schema_content, dict) else {},
            system_asset_path=sys_asset.path if sys_asset else None,
            schema_asset_path=schema_asset.path if schema_asset else None,
            system_asset_key=sys_asset.key if sys_asset else None,
            schema_asset_key=schema_asset.key if schema_asset else None,
            max_output_tokens=profile_defaults.max_output_tokens,
            max_steps=profile_defaults.max_steps,
            mode=effective_mode,
            allow_detailed=(effective_mode == "detailed"),
            allow_visuals_only_if_asked=profile_defaults.allow_visuals_only_if_asked,
            cost_multiplier=profile_defaults.cost_multiplier
        )
