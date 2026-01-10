import os
from typing import List, Tuple, Optional
from sqlmodel import Session
from app.models import Crop, User

class OCRRouterService:
    def __init__(self):
        self.vlm_daily_cap = float(os.getenv("VLM_DAILY_BUDGET_USD", "10.0"))
        self.confidence_threshold = 0.78

    def decide_engine(
        self, 
        crop: Crop, 
        user: User, 
        preferred_engine: str = "auto", 
        user_intent: str = "normal"
    ) -> Tuple[str, Optional[str], List[str]]:
        """
        Returns: (chosen_engine, vlm_type, reasons)
        """
        reasons = []
        
        # 1. Respect EXPLICIT user request if budget allows
        if preferred_engine == "vlm":
            if self._check_budget(user):
                return "vlm", "text_formula", ["USER_EXPLICIT_VLM"]
            else:
                return "local", None, ["BUDGET_BLOCKED_VLM_REQUESTED"]
        
        if preferred_engine == "local":
            return "local", None, ["USER_EXPLICIT_LOCAL"]

        # 2. AUTO Logic
        # Case A: User intent is high accuracy
        if user_intent == "high_accuracy":
            if self._check_budget(user):
                return "vlm", "text_formula", ["INTENT_HIGH_ACCURACY"]
            reasons.append("BUDGET_BLOCKED_INTENT")

        # Case B: Layout Analysis (Heuristic: Aspect Ratio or previous signals)
        # Note: If we had a fast layout-detect, we'd use it here.
        # For now, if crop is very wide or very tall, maybe it's a table?
        # (Simplified trigger)
        
        # Case C: Repeated failure trigger (impl in worker/job logic)
        
        # Default
        return "local", None, ["DEFAULT_LOCAL"]

    def _check_budget(self, user: User) -> bool:
        # Placeholder for real Redis-based budget/quota check
        # For now, Pro users get VLM, free users don't
        if user.subscription_tier in ("pro", "enterprise"):
            return True
        return False

ocr_router_service = OCRRouterService()
