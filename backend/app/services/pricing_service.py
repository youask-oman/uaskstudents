
from typing import Dict, Optional, Any, Tuple
import json
import math
from datetime import datetime
from sqlmodel import Session, select, desc
from pydantic import BaseModel, Field

from app.models import SystemConfig, SystemConfigVersion

# Default Pricing Configuration
DEFAULT_PRICING_CONFIG = {
    "credits": {
        "usd_to_credits": 25.0,
        "expiry_days": 120,
        "spend_strategy": "fifo"
    },
    "token_billing": {
        "usd_per_1000_tokens": 0.00, # Retail price rate
        "uask_fee_tokens_per_question": 700,
        "rounding": {
            "tokens_rounding": "ceil_1000",
            "credits_rounding": "ceil"
        }
    },
    "feature_costs": {
        # Legacy/Fixed costs (if needed for non-LLM actions)
        "image_import_credits": 3.0,
        "pdf_import_credits": 5.0, 
        "voice_solve_credits": 3.0, # Base cost for voice
        "voice_credits_per_second": 3.333333
    },
    "solve_pricing": {
        "pricing_version": "2026-02-01",
        "tiers": {
            "FREE": 1.0,
            "STANDARD": 2.0,
            "RESEARCH": 4.0
        },
        "addons": {
            "ocr": 1.0,
            "voice": 1.0,
            "verify": 0.0,
            "plot": 0.0
        },
        "asset_addons": {
            "none": 0.0,
            "image": 0.0,
            "pdf": 1.0
        }
    },
    "policy": {
        "max_credits_per_action": 50.0,
        "enforce_non_negative_balance": True
    }
}

class PricingConfig(BaseModel):
    credits: Dict[str, Any]
    token_billing: Dict[str, Any]
    feature_costs: Dict[str, float]
    solve_pricing: Dict[str, Any] = Field(default_factory=dict)
    # token_pricing_metadata: Dict[str, Any] # Removed/Depreciated for flattened token_billing
    policy: Dict[str, Any]
    config_version_id: Optional[int] = None

class PricingService:
    def get_pricing_config(self, session: Session) -> PricingConfig:
        """
        Retrieve pricing config from SystemConfigVersion (active) or fallback to SystemConfig.
        """
        # 1. Try to get latest version
        statement = select(SystemConfigVersion).where(
            SystemConfigVersion.config_type == "pricing"
        ).order_by(desc(SystemConfigVersion.version))
        latest = session.exec(statement).first()
        
        data = None
        version_id = None
        
        if latest:
            data = latest.value
            version_id = latest.id
        else:
            # Fallback to legacy
            config_entry = session.get(SystemConfig, "pricing")
            if config_entry:
                try:
                    data = json.loads(config_entry.value)
                except:
                    pass
            
        if not data:
            data = DEFAULT_PRICING_CONFIG.copy()
            
        try:
            # Merge with defaults for safety
            merged = DEFAULT_PRICING_CONFIG.copy()
            merged.update(data)
            config = PricingConfig(**merged)
            config.config_version_id = version_id
            return config
        except Exception as e:
            print(f"[PRICING] Error parsing pricing config: {e}. Using defaults.")
            return PricingConfig(**DEFAULT_PRICING_CONFIG)

    def calculate_estimate_token_cost(
        self, 
        action_type: str, 
        estimated_input: int, 
        estimated_output: int, 
        session: Session
    ) -> Tuple[float, float, int, int, Optional[int]]:
        """
        Calculate Estimated Cost.
        Returns: (estimated_credits, estimated_usd, estimated_billable_tokens, fee_tokens, config_version_id)
        """
        config = self.get_pricing_config(session)
        tb = config.token_billing
        
        # 1. Base Tokens
        total_raw_tokens = estimated_input + estimated_output
        
        # 2. Add Fee (only for solve actions)
        fee_tokens = 0
        if "solve" in action_type:
            fee_tokens = tb.get("uask_fee_tokens_per_question", 700)
            
        billable_tokens = total_raw_tokens + fee_tokens
        
        # 3. Rounding
        rounding_rule = tb.get("rounding", {}).get("tokens_rounding", "ceil_1000")
        if rounding_rule == "ceil_1000":
             units_1000 = math.ceil(billable_tokens / 1000.0)
        else:
             units_1000 = billable_tokens / 1000.0
             
        # 4. USD Calculation
        usd_rate = tb.get("usd_per_1000_tokens", 0.00)
        estimated_usd = units_1000 * usd_rate
        
        # 5. Credits Calculation
        usd_to_credits = config.credits.get("usd_to_credits", 25.0)
        raw_credits = estimated_usd * usd_to_credits
        
        credits_round_rule = tb.get("rounding", {}).get("credits_rounding", "ceil")
        if credits_round_rule == "ceil":
            estimated_credits = math.ceil(raw_credits)
        else:
            estimated_credits = raw_credits
            
        return float(estimated_credits), estimated_usd, billable_tokens, fee_tokens, config.config_version_id

    def calculate_actual_token_cost(
        self, 
        action_type: str, 
        actual_input: int, 
        actual_output: int, 
        session: Session
    ) -> Tuple[float, float, int, int, Optional[int]]:
        """
        Calculate Actual Cost (Reconciliation).
        Returns: (actual_credits, actual_usd, actual_billable_tokens, fee_tokens, config_version_id)
        Logic mirrors estimate but uses actuals.
        """
        # Reuse same logic, just inputs differ
        return self.calculate_estimate_token_cost(action_type, actual_input, actual_output, session)

    def calculate_legacy_cost(self, action_type: str, session: Session, **kwargs) -> float:
        """
        Fallback for non-token actions (like pure Import if configured as fixed, or Voice transcription base)
        """
        config = self.get_pricing_config(session)
        costs = config.feature_costs
        
        cost = 0.0
        
        if action_type == "image_import":
            cost = costs.get("image_import_credits", 3.0)
        elif action_type == "pdf_import":
            cost = costs.get("pdf_import_credits", 5.0)
        elif action_type == "voice_total":
            # Transcription logic
             duration_sec = kwargs.get("duration", 0.0)
             rate = costs.get("voice_credits_per_second", 3.333333)
             base_solve = costs.get("voice_solve_credits", 3.0)
             cost = math.ceil(duration_sec * rate) + base_solve
             
        return float(cost)

pricing_service = PricingService()
