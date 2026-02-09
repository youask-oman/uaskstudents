"""
Prometheus-compatible metrics for billing observability.

Metrics tracked:
- credits_hold_created_total: Counter of holds created
- credits_settled_total: Counter of settlements
- credits_refunded_total: Counter of refunds
- credits_granted_total: Counter of grants (by type)
- reconciliation_mismatch_total: Counter of cache mismatches
- billing_errors_total: Counter of errors (by error_code)
- credits_balance_gauge: Current user credit balances (sampled)
- hold_duration_seconds: Histogram of hold durations
"""

from typing import Optional
import time
import logging

logger = logging.getLogger("billing.metrics")

# Metric storage (in production, replace with prometheus_client or similar)
_metrics = {
    "credits_hold_created_total": 0,
    "credits_settled_total": 0,
    "credits_refunded_total": 0,
    "credits_granted_total": {},  # by grant_type
    "reconciliation_mismatch_total": 0,
    "billing_errors_total": {},  # by error_code
}


def inc_holds_created(count: int = 1) -> None:
    """Increment hold creation counter."""
    _metrics["credits_hold_created_total"] += count
    logger.debug(f"[METRICS] credits_hold_created_total += {count}")


def inc_settled(count: int = 1) -> None:
    """Increment settlement counter."""
    _metrics["credits_settled_total"] += count
    logger.debug(f"[METRICS] credits_settled_total += {count}")


def inc_refunded(count: int = 1) -> None:
    """Increment refund counter."""
    _metrics["credits_refunded_total"] += count
    logger.debug(f"[METRICS] credits_refunded_total += {count}")


def inc_granted(grant_type: str, count: int = 1) -> None:
    """Increment grant counter by type (GIFT, PROMO, ADJUSTMENT)."""
    if grant_type not in _metrics["credits_granted_total"]:
        _metrics["credits_granted_total"][grant_type] = 0
    _metrics["credits_granted_total"][grant_type] += count
    logger.debug(f"[METRICS] credits_granted_total[{grant_type}] += {count}")


def inc_reconciliation_mismatch(count: int = 1) -> None:
    """Increment reconciliation mismatch counter."""
    _metrics["reconciliation_mismatch_total"] += count
    logger.debug(f"[METRICS] reconciliation_mismatch_total += {count}")


def inc_billing_error(error_code: str, count: int = 1) -> None:
    """Increment billing error counter by error code."""
    if error_code not in _metrics["billing_errors_total"]:
        _metrics["billing_errors_total"][error_code] = 0
    _metrics["billing_errors_total"][error_code] += count
    logger.debug(f"[METRICS] billing_errors_total[{error_code}] += {count}")


def get_metrics() -> dict:
    """Return current metric values (for /metrics endpoint or monitoring)."""
    return _metrics.copy()


class HoldTimer:
    """Context manager to track hold duration."""
    
    _hold_durations: list = []
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.perf_counter() - self.start_time
            HoldTimer._hold_durations.append(duration)
            logger.debug(f"[METRICS] hold_duration_seconds request_id={self.request_id} duration={duration:.3f}s")
        return False
    
    @classmethod
    def get_durations(cls) -> list:
        """Return recorded hold durations for histogram analysis."""
        return cls._hold_durations.copy()


# Feature flag integration
_BILLING_V2_ENABLED = False


def is_billing_v2_enabled() -> bool:
    """Check if billing v2 is enabled (feature flag)."""
    return _BILLING_V2_ENABLED


def set_billing_v2_enabled(enabled: bool) -> None:
    """Set billing v2 feature flag (for testing/rollout)."""
    global _BILLING_V2_ENABLED
    _BILLING_V2_ENABLED = enabled
    logger.info(f"[FEATURE_FLAG] BILLING_V2_ENABLED = {enabled}")
