from pydantic import BaseModel
from typing import Optional
import os

class PromptProfile(BaseModel):
    tier: str
    # Paths are optional now if content is provided directly
    system_relative_path: Optional[str] = None
    schema_relative_path: Optional[str] = None
    
    # Direct Content (populated by resolver)
    system_prompt_content: Optional[str] = None
    json_schema_content: Optional[dict] = None
    system_asset_path: Optional[str] = None
    schema_asset_path: Optional[str] = None
    system_asset_key: Optional[str] = None
    schema_asset_key: Optional[str] = None
    
    max_output_tokens: int
    max_steps: int
    allow_visuals_only_if_asked: bool = True
    allow_detailed: bool = False
    
    # Accounting / Ledger
    mode: str = "minimal" # minimal or detailed
    cost_multiplier: float = 1.0

    @property
    def system_full_path(self) -> str:
        # Assuming this file is in backend/app/llm_profiles/profiles.py
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, self.system_relative_path)

    @property
    def schema_full_path(self) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, self.schema_relative_path)

def get_profile_free() -> PromptProfile:
    return PromptProfile(
        tier="free",
        system_relative_path="free/system.txt",
        schema_relative_path="free/schema.json",
        system_asset_path="llm_profiles/free/system.txt",
        schema_asset_path="llm_profiles/free/schema.json",
        system_asset_key="free:system",
        schema_asset_key="free:schema",
        max_output_tokens=450,  # Legacy fallback, resolver should override
        max_steps=2,            # Legacy fallback
        allow_visuals_only_if_asked=True,
        allow_detailed=False
    )

def get_profile_standard() -> PromptProfile:
    # Standard users get the full V3 experience
    return PromptProfile(
        tier="standard",
        system_relative_path="../static_design/solver_system.txt", # Pointing to existing V3 prompt location or new standard loc
        schema_relative_path="../schemas/na_math_solver_v3.py", # OR pointing to a json schema file if we convert
        # ACTUALLY: The current solver uses python schemas dynamically, but for uniformity we might want JSON assets.
        # However, for now, let's keep standard pointing to where it was, but we might need to adjust logic to handle .py vs .json or 
        # just standardize on reading text/json files.
        # To strictly follow the plan "Recreate backend/app/llm_profiles/free/schema.json", we are making JSONs.
        # Let's assume standard also gets moved or routed. 
        # FOR NOW: Let's point standard to a placeholder or existing. 
        # The plan said: "Implement get_profile_standard() (stub)". 
        # I will point it to the canonical prompt locations for now, but usually V3 uses the code-defined schema.
        # Let's stub it to use the new structure if we migrate, or keep it compatible.
        max_output_tokens=4096,
        max_steps=15,
        allow_visuals_only_if_asked=False, # Always allow if relevant
        allow_detailed=True
    )
    # NOTE: The standard profile implementation details might vary depending on if we migrate the main solver to use this system entirely.
    # For this task, we focus on FREE tier.

def get_prompt_profile(tier: str) -> PromptProfile:
    tier = tier.lower()
    if tier == "free":
        return get_profile_free()
    elif tier in ["standard", "pro", "premium"]:
        return get_profile_standard() # Fallback to standard for now
    else:
        return get_profile_free() # Default safer option
