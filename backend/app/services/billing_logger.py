"""
Centralized structured logging for all billing events.

Provides a consistent logging interface for:
- Credit holds, settlements, releases
- Refunds, grants, adjustments
- Reconciliation events
- Errors and anomalies

All logs include: event_type, user_id, request_id, attempt_id,
delta_credits, balance_before, balance_after, success/failure.
"""

import logging
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger("billing")


@dataclass
class BillingEvent:
    """Structured billing event for logging."""
    event_type: str  # HOLD_CREATED, HOLD_RELEASED, SETTLED, REFUNDED, GRANT, ADJUSTMENT, ERROR
    user_id: int
    request_id: Optional[str] = None
    attempt_id: Optional[str] = None
    payment_id: Optional[str] = None
    invoice_id: Optional[int] = None
    delta_credits: Optional[Decimal] = None
    delta_usd: Optional[Decimal] = None
    balance_before_cached: Optional[Decimal] = None
    balance_after_cached: Optional[Decimal] = None
    balance_before_computed: Optional[Decimal] = None
    balance_after_computed: Optional[Decimal] = None
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


def _decimal_serializer(obj):
    """JSON serializer for Decimal types."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def emit_billing_event(event: BillingEvent) -> None:
    """
    Emit a structured billing event to the logging system.
    
    All billing operations should call this for observability.
    """
    event_dict = asdict(event)
    
    # Format for structured logging
    log_line = json.dumps(event_dict, default=_decimal_serializer)
    
    if event.success:
        logger.info(f"[BILLING] {log_line}")
    else:
        logger.error(f"[BILLING_ERROR] {log_line}")


def log_hold_created(
    user_id: int,
    request_id: str,
    reserved_credits: Decimal,
    balance_before: Decimal,
    attempt_id: Optional[str] = None,
) -> None:
    """Log a credit hold creation."""
    emit_billing_event(BillingEvent(
        event_type="HOLD_CREATED",
        user_id=user_id,
        request_id=request_id,
        attempt_id=attempt_id,
        delta_credits=-reserved_credits,
        balance_before_cached=balance_before,
        balance_after_cached=balance_before - reserved_credits,
        success=True,
    ))


def log_hold_released(
    user_id: int,
    request_id: str,
    released_credits: Decimal,
    balance_after: Decimal,
    attempt_id: Optional[str] = None,
) -> None:
    """Log a credit hold release (no net charge)."""
    emit_billing_event(BillingEvent(
        event_type="HOLD_RELEASED",
        user_id=user_id,
        request_id=request_id,
        attempt_id=attempt_id,
        delta_credits=released_credits,
        balance_after_cached=balance_after,
        success=True,
    ))


def log_settled(
    user_id: int,
    request_id: str,
    credits_charged: Decimal,
    usd_charged: Decimal,
    balance_before: Decimal,
    balance_after: Decimal,
    attempt_id: Optional[str] = None,
    invoice_id: Optional[int] = None,
) -> None:
    """Log a successful settlement (credit consumption)."""
    emit_billing_event(BillingEvent(
        event_type="SETTLED",
        user_id=user_id,
        request_id=request_id,
        attempt_id=attempt_id,
        invoice_id=invoice_id,
        delta_credits=-credits_charged,
        delta_usd=-usd_charged,
        balance_before_cached=balance_before,
        balance_after_cached=balance_after,
        success=True,
    ))


def log_refunded(
    user_id: int,
    credits_refunded: Decimal,
    payment_id: Optional[str] = None,
    request_id: Optional[str] = None,
    reason_code: Optional[str] = None,
) -> None:
    """Log a refund (credit lot creation)."""
    emit_billing_event(BillingEvent(
        event_type="REFUNDED",
        user_id=user_id,
        request_id=request_id,
        payment_id=payment_id,
        delta_credits=credits_refunded,
        success=True,
        metadata={"reason_code": reason_code} if reason_code else None,
    ))


def log_grant(
    user_id: int,
    credits_granted: Decimal,
    grant_type: str,  # GIFT, PROMO, ADJUSTMENT
    program_id: Optional[int] = None,
) -> None:
    """Log a credit grant (gift, promo, adjustment)."""
    emit_billing_event(BillingEvent(
        event_type="GRANT",
        user_id=user_id,
        delta_credits=credits_granted,
        success=True,
        metadata={"grant_type": grant_type, "program_id": program_id},
    ))


def log_reconciliation_mismatch(
    user_id: int,
    cached_balance: Decimal,
    computed_balance: Decimal,
    delta: Decimal,
    auto_fixed: bool = False,
) -> None:
    """Log a reconciliation mismatch."""
    emit_billing_event(BillingEvent(
        event_type="RECONCILIATION_MISMATCH",
        user_id=user_id,
        balance_before_cached=cached_balance,
        balance_after_computed=computed_balance,
        delta_credits=delta,
        success=True,
        metadata={"auto_fixed": auto_fixed},
    ))


def log_billing_error(
    user_id: int,
    error_code: str,
    error_message: str,
    request_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a billing error."""
    emit_billing_event(BillingEvent(
        event_type="ERROR",
        user_id=user_id,
        request_id=request_id,
        attempt_id=attempt_id,
        success=False,
        error_code=error_code,
        error_message=error_message,
        metadata=metadata,
    ))
