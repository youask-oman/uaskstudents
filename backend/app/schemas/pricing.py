from pydantic import BaseModel, Field, model_validator
from typing import Dict, Optional

# --- Multipliers Schema ---

class TierPricingConfig(BaseModel):
    """Credit cost for a specific action in a specific tier."""
    text: int = Field(default=1, description="Base cost for text-only solve")
    snap_image: int = Field(default=2, description="Base cost for image crop solve")
    snap_pdf: int = Field(default=3, description="Base cost for PDF crop solve")
    voice: int = Field(default=2, description="Base cost for voice interaction")

class SolveCreditsConfig(BaseModel):
    """Credit costs for the 'solve' action across different tiers."""
    short_steps: TierPricingConfig = Field(default_factory=lambda: TierPricingConfig(text=1, snap_image=2, snap_pdf=3, voice=2))
    final: TierPricingConfig = Field(default_factory=lambda: TierPricingConfig(text=1, snap_image=2, snap_pdf=3, voice=2))
    standard: TierPricingConfig = Field(default_factory=lambda: TierPricingConfig(text=2, snap_image=3, snap_pdf=4, voice=3))
    research: TierPricingConfig = Field(default_factory=lambda: TierPricingConfig(text=4, snap_image=5, snap_pdf=6, voice=5))

    @model_validator(mode="before")
    @classmethod
    def _ingest_legacy_keys(cls, raw):
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "short_steps" not in data and "free" in data:
            data["short_steps"] = data["free"]
        if "final" not in data and "short" in data:
            data["final"] = data["short"]
        return data

class VerifyCreditsConfig(BaseModel):
    """Credit costs for the 'verify' action."""
    short_steps: int = 1
    final: int = 1
    standard: int = 1
    research: int = 2

    @model_validator(mode="before")
    @classmethod
    def _ingest_legacy_keys(cls, raw):
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "short_steps" not in data and "free" in data:
            data["short_steps"] = data["free"]
        if "final" not in data and "short" in data:
            data["final"] = data["short"]
        return data

class CreditsConfig(BaseModel):
    """Root container for all credit pricing."""
    solve: SolveCreditsConfig = Field(default_factory=SolveCreditsConfig)
    verify: VerifyCreditsConfig = Field(default_factory=VerifyCreditsConfig)
    plot_trigger: int = Field(default=0, description="Cost to trigger a plot")
    plot_spec: int = Field(default=1, description="Cost to generate plot specification")

class PlanMultipliers(BaseModel):
    """
    Schema for the 'plan.multipliers' JSON column.
    
    Example:
    {
      "version": 1,
      "credits": { ... }
    }
    """
    version: int = Field(default=1)
    credits: CreditsConfig = Field(default_factory=CreditsConfig)


# --- Features Schema ---

class PlanFeatures(BaseModel):
    """
    Schema for the 'plan.features' JSON column.
    Defines capabilities and caps.
    """
    # Gates
    allow_research: bool = Field(default=False, description="Access to Research tier prompts")
    allow_verify: bool = Field(default=True, description="Access to verification Step")
    allow_plot: bool = Field(default=True, description="Access to plotting tools")
    
    # Caps
    daily_credit_cap: int = Field(default=50, description="Max credits spendable per day")
    ocr_monthly_cap: int = Field(default=100, description="Max OCR pages/crops per month")
    voice_monthly_cap: int = Field(default=50, description="Max voice sessions per month")
    generated_images_monthly_cap: int = Field(default=20, description="Max image generations per month")
    make_it_right_monthly_cap: int = Field(default=5, description="Number of free 'Make it Right' corrections")
