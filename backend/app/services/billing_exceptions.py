"""
Domain-specific exceptions for billing operations.

These exceptions provide clear semantics for billing errors
and enable proper error handling in API layers.
"""

from typing import Optional, Dict, Any


class BillingError(Exception):
    """Base exception for all billing errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_id = user_id
        self.request_id = request_id
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class InsufficientCreditsError(BillingError):
    """Raised when user does not have enough credits for an operation."""
    
    def __init__(
        self,
        user_id: int,
        required: float,
        available: float,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message=f"Insufficient credits. Required: {required}, Available: {available}",
            error_code="INSUFFICIENT_CREDITS",
            user_id=user_id,
            request_id=request_id,
            details={"required": required, "available": available},
        )
        self.required = required
        self.available = available


class IdempotencyConflictError(BillingError):
    """Raised when an idempotency key has already been used."""
    
    def __init__(
        self,
        idempotency_key: str,
        existing_status: str,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message=f"Idempotency conflict: key '{idempotency_key}' already processed with status '{existing_status}'",
            error_code="IDEMPOTENCY_CONFLICT",
            request_id=request_id,
            details={"idempotency_key": idempotency_key, "existing_status": existing_status},
        )
        self.idempotency_key = idempotency_key
        self.existing_status = existing_status


class HoldNotFoundError(BillingError):
    """Raised when a hold cannot be found for settlement/release."""
    
    def __init__(self, request_id: str, user_id: Optional[int] = None):
        super().__init__(
            message=f"Hold not found for request_id: {request_id}",
            error_code="HOLD_NOT_FOUND",
            user_id=user_id,
            request_id=request_id,
        )


class HoldAlreadyFinalizedError(BillingError):
    """Raised when attempting to settle/release an already finalized hold."""
    
    def __init__(self, request_id: str, current_status: str):
        super().__init__(
            message=f"Hold already finalized for request_id: {request_id} (status: {current_status})",
            error_code="HOLD_ALREADY_FINALIZED",
            request_id=request_id,
            details={"current_status": current_status},
        )
        self.current_status = current_status


class InvalidRefundSourceError(BillingError):
    """Raised when a refund references an invalid source."""
    
    def __init__(
        self,
        reason: str,
        source_payment_id: Optional[str] = None,
        source_attempt_id: Optional[str] = None,
    ):
        super().__init__(
            message=f"Invalid refund source: {reason}",
            error_code="INVALID_REFUND_SOURCE",
            details={
                "reason": reason,
                "source_payment_id": source_payment_id,
                "source_attempt_id": source_attempt_id,
            },
        )


class PaymentNotSettledError(BillingError):
    """Raised when attempting to refund a payment that hasn't settled."""
    
    def __init__(self, payment_id: str, current_status: str):
        super().__init__(
            message=f"Payment {payment_id} not settled (status: {current_status})",
            error_code="PAYMENT_NOT_SETTLED",
            details={"payment_id": payment_id, "current_status": current_status},
        )
        self.payment_id = payment_id
        self.current_status = current_status


class CreditLotExhaustedError(BillingError):
    """Raised when a credit lot is exhausted during allocation."""
    
    def __init__(self, lot_id: int, remaining: float, requested: float):
        super().__init__(
            message=f"Credit lot {lot_id} exhausted. Remaining: {remaining}, Requested: {requested}",
            error_code="CREDIT_LOT_EXHAUSTED",
            details={"lot_id": lot_id, "remaining": remaining, "requested": requested},
        )


class ReconciliationError(BillingError):
    """Raised when reconciliation detects an unrecoverable issue."""
    
    def __init__(self, user_id: int, cached: float, computed: float, delta: float):
        super().__init__(
            message=f"Reconciliation error for user {user_id}: cached={cached}, computed={computed}, delta={delta}",
            error_code="RECONCILIATION_ERROR",
            user_id=user_id,
            details={"cached": cached, "computed": computed, "delta": delta},
        )
