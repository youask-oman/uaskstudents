"""
Feature Flags for Billing V2.

This module provides feature flag management for the billing system redesign.
Flags can be controlled via environment variables or a feature flag service.

Usage:
    from app.services.billing_feature_flags import is_billing_v2_enabled
    
    if is_billing_v2_enabled(user_id):
        # Use new billing service
    else:
        # Use legacy billing service
"""

import os
from typing import Optional
from functools import lru_cache


class BillingFeatureFlags:
    """
    Feature flag manager for billing V2.
    
    Supports:
    - Global enable/disable via environment variables
    - Progressive rollout by user ID percentage
    - Admin override
    """
    
    def __init__(self):
        # Default values from environment
        self._billing_v2 = os.environ.get("BILLING_V2_ENABLED", "false").lower() == "true"
        self._credit_programs = os.environ.get("CREDIT_PROGRAMS_ENABLED", "false").lower() == "true"
        self._refund_v2 = os.environ.get("REFUND_V2_ENABLED", "false").lower() == "true"
        self._reconciliation_autofix = os.environ.get("RECONCILIATION_AUTOFIX_ENABLED", "false").lower() == "true"
        
        # Rollout percentage (0-100)
        self._v2_rollout_percent = int(os.environ.get("BILLING_V2_ROLLOUT_PERCENT", "0"))
        
        # Admin user IDs always get V2
        admin_ids_str = os.environ.get("BILLING_V2_ADMIN_IDS", "")
        self._admin_ids = set(int(x) for x in admin_ids_str.split(",") if x.strip())
    
    def is_billing_v2_enabled(self, user_id: Optional[int] = None) -> bool:
        """
        Check if Billing V2 is enabled for a user.
        
        Rollout precedence:
        1. Global flag disabled -> False
        2. User is admin -> True
        3. User ID is within rollout percentage -> True
        4. Otherwise -> False
        """
        if not self._billing_v2:
            return False
        
        if user_id is None:
            return True  # Global context, flag is on
        
        # Admin override
        if user_id in self._admin_ids:
            return True
        
        # Progressive rollout by user ID hash
        if self._v2_rollout_percent >= 100:
            return True
        
        if self._v2_rollout_percent <= 0:
            return False
        
        # Deterministic hash for consistent user experience
        bucket = user_id % 100
        return bucket < self._v2_rollout_percent
    
    def is_credit_programs_enabled(self, user_id: Optional[int] = None) -> bool:
        """Check if Credit Programs feature is enabled."""
        if not self._credit_programs:
            return False
        
        # Credit programs require V2 to be enabled
        return self.is_billing_v2_enabled(user_id)
    
    def is_refund_v2_enabled(self, user_id: Optional[int] = None) -> bool:
        """Check if Refund V2 semantics are enabled."""
        if not self._refund_v2:
            return False
        
        return self.is_billing_v2_enabled(user_id)
    
    def is_reconciliation_autofix_enabled(self) -> bool:
        """Check if reconciliation auto-fix is enabled."""
        return self._reconciliation_autofix
    
    def reload_from_env(self):
        """Reload flags from environment (useful for testing)."""
        self.__init__()


# Global singleton
_feature_flags = BillingFeatureFlags()


# Convenience functions
def is_billing_v2_enabled(user_id: Optional[int] = None) -> bool:
    """Check if Billing V2 is enabled for a user."""
    return _feature_flags.is_billing_v2_enabled(user_id)


def is_credit_programs_enabled(user_id: Optional[int] = None) -> bool:
    """Check if Credit Programs feature is enabled."""
    return _feature_flags.is_credit_programs_enabled(user_id)


def is_refund_v2_enabled(user_id: Optional[int] = None) -> bool:
    """Check if Refund V2 semantics are enabled."""
    return _feature_flags.is_refund_v2_enabled(user_id)


def is_reconciliation_autofix_enabled() -> bool:
    """Check if reconciliation auto-fix is enabled."""
    return _feature_flags.is_reconciliation_autofix_enabled()


def get_feature_flags() -> BillingFeatureFlags:
    """Get the global feature flags instance."""
    return _feature_flags
