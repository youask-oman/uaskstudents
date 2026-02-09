"""
Refund Service: Handles credit refund creation.

This service implements:
1. Refund lot creation with fresh expiry windows
2. Source tracking (payment_id, attempt_id)
3. Idempotency via refund_id
4. Special handling for unused top-up reversals

Phase 4 of Billing Redesign.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

from app.models import CreditLot, User
from app.services.billing_logger import log_refunded, log_billing_error
from app.services.billing_metrics import inc_refunded, inc_billing_error
from app.services.billing_exceptions import (
    InvalidRefundSourceError,
    IdempotencyConflictError,
)


# Configuration
DEFAULT_REFUND_EXPIRY_DAYS = 60
DEFAULT_TOPUP_EXPIRY_DAYS = 365


class RefundService:
    """
    Manages credit refund operations.
    
    Refund Rules:
    1. Refunds ALWAYS create a new CreditLot(type=REFUND)
    2. Default expiry: fresh window (60 days from now)
    3. Exception: Unused top-up reversals use top-up expiry window (365 days)
    4. All refunds must be idempotent by refund_id
    """
    
    def create_refund(
        self,
        session: Session,
        user_id: int,
        credits: Decimal,
        refund_id: str,
        reason_code: str,
        source_payment_id: Optional[str] = None,
        source_attempt_id: Optional[str] = None,
        source_ledger_event_id: Optional[int] = None,
        is_topup_reversal: bool = False,
    ) -> CreditLot:
        """
        Create a refund credit lot.
        
        Args:
            session: Database session
            user_id: User to refund credits to
            credits: Amount of credits to refund
            refund_id: Unique ID for idempotency (e.g., Stripe refund ID)
            reason_code: Reason for refund (e.g., "action_failed", "user_request")
            source_payment_id: Original payment ID if applicable
            source_attempt_id: Original attempt ID if applicable
            source_ledger_event_id: Original ledger event ID if applicable
            is_topup_reversal: If True, use top-up expiry window
        
        Returns:
            Created CreditLot
        
        Raises:
            IdempotencyConflictError: If refund_id already exists
        """
        credits = Decimal(str(credits))
        
        # 1. Idempotency check
        existing = session.exec(
            select(CreditLot)
            .where(
                CreditLot.external_ref == refund_id,
                CreditLot.lot_type == "REFUND",
            )
        ).first()
        
        if existing:
            # Idempotent return
            return existing
        
        # 2. Validate user exists
        user = session.get(User, user_id)
        if not user:
            log_billing_error(
                user_id=user_id,
                error_code="USER_NOT_FOUND",
                error_message="User not found for refund",
                metadata={"refund_id": refund_id},
            )
            inc_billing_error("USER_NOT_FOUND")
            raise ValueError(f"User {user_id} not found")
        
        # 3. Calculate expiry
        if is_topup_reversal:
            # Unused top-up reversal: use top-up expiry window
            expiry_days = DEFAULT_TOPUP_EXPIRY_DAYS
        else:
            # Default: fresh window
            expiry_days = DEFAULT_REFUND_EXPIRY_DAYS
        
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        # 4. Create refund lot
        lot = CreditLot(
            user_id=user_id,
            credits_total=credits,
            credits_remaining=credits,
            lot_type="REFUND",
            status="ACTIVE",
            source="REFUND",
            external_ref=refund_id,
            source_payment_id=source_payment_id,
            source_attempt_id=source_attempt_id,
            reason_code=reason_code,
            expires_at=expires_at,
            purchased_at=datetime.utcnow(),
        )
        session.add(lot)
        session.flush()
        
        # 5. Log and metrics
        log_refunded(
            user_id=user_id,
            credits_refunded=credits,
            payment_id=source_payment_id,
            request_id=source_attempt_id,
            reason_code=reason_code,
        )
        inc_refunded()
        
        return lot
    
    def create_solve_failure_refund(
        self,
        session: Session,
        user_id: int,
        credits: Decimal,
        request_id: str,
        attempt_id: Optional[str] = None,
    ) -> CreditLot:
        """
        Create a refund for a failed solve action.
        
        This is a convenience method for the common case of
        refunding credits when a solve fails after billing.
        """
        refund_id = f"solve_fail_{request_id}"
        
        return self.create_refund(
            session=session,
            user_id=user_id,
            credits=credits,
            refund_id=refund_id,
            reason_code="solve_failed",
            source_attempt_id=attempt_id or request_id,
            is_topup_reversal=False,
        )
    
    def create_stripe_refund(
        self,
        session: Session,
        user_id: int,
        credits: Decimal,
        stripe_refund_id: str,
        stripe_payment_intent_id: str,
        is_full_refund: bool = True,
    ) -> CreditLot:
        """
        Create a refund from a Stripe refund event.
        
        Args:
            session: Database session
            user_id: User to refund
            credits: Amount of credits
            stripe_refund_id: Stripe refund ID (for idempotency)
            stripe_payment_intent_id: Original payment intent
            is_full_refund: Whether this is a full or partial refund
        """
        reason_code = "stripe_full_refund" if is_full_refund else "stripe_partial_refund"
        
        return self.create_refund(
            session=session,
            user_id=user_id,
            credits=credits,
            refund_id=stripe_refund_id,
            reason_code=reason_code,
            source_payment_id=stripe_payment_intent_id,
            is_topup_reversal=is_full_refund,  # Full refunds get topup expiry
        )


# Singleton
refund_service = RefundService()
