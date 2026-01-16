"""
OCR Router Service
==================
Determines which OCR engine to use based on:
1. OCR_ENGINE environment variable (master override)
2. User explicit preference
3. User subscription tier
4. User intent (high_accuracy, etc.)
"""

import os
from typing import List, Tuple, Optional
from sqlmodel import Session
from app.models import Crop, User

class OCRRouterService:
    def __init__(self):
        self.vlm_daily_cap = float(os.getenv("VLM_DAILY_BUDGET_USD", "10.0"))
        self.confidence_threshold = 0.78

    def get_env_engine(self) -> str:
        """Get engine preference from environment variable."""
        return os.getenv("OCR_ENGINE", "vlm").lower()

    def decide_engine(
        self, 
        crop: Crop, 
        user: User, 
        preferred_engine: str = "auto", 
        user_intent: str = "normal"
    ) -> Tuple[str, Optional[str], List[str]]:
        """
        Determine which OCR engine to use.
        
        Returns: (chosen_engine, vlm_type, reasons)
        
        Priority:
        1. OCR_ENGINE env var (if not "auto")
        2. User explicit preference (if not "auto")
        3. Routing logic (intent, budget, subscription)
        """
        reasons = []
        env_engine = self.get_env_engine()
        
        # ============================================================
        # MASTER OVERRIDE: If OCR_ENGINE env var is explicitly set to
        # "vlm" or "local", use that regardless of other logic.
        # This allows operators to force a specific engine globally.
        # ============================================================
        if env_engine == "vlm":
            return "vlm", "text_formula", ["ENV_OVERRIDE_VLM"]
        elif env_engine == "local":
            return "local", None, ["ENV_OVERRIDE_LOCAL"]
        
        # If env_engine == "auto", continue with routing logic below
        
        # ============================================================
        # USER EXPLICIT REQUEST
        # ============================================================
        if preferred_engine == "vlm":
            if self._check_budget(user):
                return "vlm", "text_formula", ["USER_EXPLICIT_VLM"]
            else:
                return "local", None, ["BUDGET_BLOCKED_VLM_REQUESTED"]
        
        if preferred_engine == "local":
            return "local", None, ["USER_EXPLICIT_LOCAL"]

        # ============================================================
        # AUTO ROUTING LOGIC
        # ============================================================
        
        # Case A: User intent is high accuracy
        if user_intent == "high_accuracy":
            if self._check_budget(user):
                return "vlm", "text_formula", ["INTENT_HIGH_ACCURACY"]
            reasons.append("BUDGET_BLOCKED_INTENT")

        # Case B: Pro/Enterprise users default to VLM
        if self._check_budget(user):
            return "vlm", "text_formula", ["SUBSCRIPTION_VLM"]
        
        # Default: Local engine
        return "local", None, ["DEFAULT_LOCAL"]

    def _check_budget(self, user: User) -> bool:
        """
        Check if user has budget for VLM usage.
        
        Returns True for:
        - Pro/Enterprise subscribers
        - Users with remaining VLM quota
        """
        if user.subscription_tier in ("pro", "enterprise"):
            return True
        return False

ocr_router_service = OCRRouterService()
