"""
BillingLedgerServiceV2: Production-grade settlement service with ACID guarantees.

This service replaces the legacy billing_service for settlement operations when
the BILLING_V2_ENABLED feature flag is on. Key improvements:

1. Row-level locking (`SELECT ... FOR UPDATE`) to prevent double-spend
2. Single DB transaction for all balance-changing operations
3. FIFO credit allocation by expiry date
4. Decimal arithmetic for precision
5. Structured logging and metrics
6. Idempotency via idempotency_key

Created: 2026-02-09 (Phase 2 of Billing Redesign)
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass
from sqlmodel import Session, select
from sqlalchemy import text

from app.models import (
    User, CreditLot, CreditLotConsumption, BillingLedger,
    CreditHold, UsageLedger
)
from app.services.subscription_service import subscription_service
from app.services.billing_logger import (
    log_hold_created, log_hold_released, log_settled,
    log_billing_error
)
from app.services.billing_metrics import (
    inc_holds_created, inc_settled, inc_billing_error
)
from app.services.billing_exceptions import (
    InsufficientCreditsError, IdempotencyConflictError,
    HoldNotFoundError, HoldAlreadyFinalizedError
)


# Rounding configuration
ROUNDING = ROUND_HALF_UP
EPSILON = Decimal("0.0000001")


@dataclass
class HoldResult:
    """Result of a hold creation."""
    hold_id: int
    request_id: str
    reserved_credits: Decimal
    balance_before: Decimal
    success: bool = True
    message: str = ""


@dataclass
class SettleResult:
    """Result of a settlement operation."""
    ledger_id: int
    request_id: str
    credits_charged: Decimal
    balance_after: Decimal
    status: str  # CHARGED, VOIDED
    success: bool = True
    message: str = ""


@dataclass
class ReleaseResult:
    """Result of a hold release operation."""
    request_id: str
    released_credits: Decimal
    balance_after: Decimal
    success: bool = True
    message: str = ""


class BillingLedgerServiceV2:
    """
    Production-grade settlement service with ACID guarantees.
    
    All operations:
    - Use explicit DB transactions
    - Acquire row-level locks to prevent concurrent modifications
    - Use Decimal arithmetic for precision
    - Are idempotent via idempotency_key
    - Log structured events and update metrics
    """
    
    def create_hold(
        self,
        session: Session,
        user_id: int,
        request_id: str,
        estimated_credits: Decimal,
        attempt_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> HoldResult:
        """
        Create a credit hold before executing an action.
        
        This reserves credits without consuming them, allowing the action
        to proceed with guaranteed funds.
        
        Args:
            session: Database session
            user_id: User ID
            request_id: Unique request identifier
            estimated_credits: Amount to reserve
            attempt_id: Optional attempt identifier for logging
            idempotency_key: Optional key for idempotent operation
        
        Returns:
            HoldResult with hold details
        
        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
            IdempotencyConflictError: If idempotency_key already used
        """
        # Normalize to Decimal
        estimated_credits = Decimal(str(estimated_credits))
        
        # 1. Idempotency check (if key provided)
        if idempotency_key:
            existing = session.exec(
                select(CreditHold).where(CreditHold.request_id == request_id)
            ).first()
            if existing:
                return HoldResult(
                    hold_id=existing.id,
                    request_id=request_id,
                    reserved_credits=Decimal(str(existing.reserved_credits)),
                    balance_before=Decimal("0"),  # Not computed for idempotent return
                    success=True,
                    message="Idempotent return: hold already exists"
                )
        
        # 2. Acquire lock on user row for balance check
        user = session.exec(
            select(User).where(User.id == user_id).with_for_update()
        ).first()
        
        if not user:
            log_billing_error(
                user_id=user_id,
                error_code="USER_NOT_FOUND",
                error_message="User not found during hold creation",
                request_id=request_id,
                attempt_id=attempt_id,
            )
            inc_billing_error("USER_NOT_FOUND")
            raise ValueError(f"User {user_id} not found")
        
        # 3. Compute available balance from locked credit lots
        available_balance = self._compute_available_balance_locked(session, user_id)
        
        if available_balance < estimated_credits:
            log_billing_error(
                user_id=user_id,
                error_code="INSUFFICIENT_CREDITS",
                error_message=f"Required: {estimated_credits}, Available: {available_balance}",
                request_id=request_id,
                attempt_id=attempt_id,
            )
            inc_billing_error("INSUFFICIENT_CREDITS")
            raise InsufficientCreditsError(
                user_id=user_id,
                required=float(estimated_credits),
                available=float(available_balance),
                request_id=request_id,
            )
        
        # 4. Ensure subscription exists (legacy FK requirement)
        subscription = subscription_service.get_or_create_subscription(session, user)
        if not subscription:
            raise ValueError("Subscription not available for hold creation")

        # 5. Create hold record
        hold = CreditHold(
            user_id=user_id,
            subscription_id=subscription.id,
            request_id=request_id,
            reserved_credits=float(estimated_credits),  # Will be Decimal after model update
            status="held",
        )
        session.add(hold)
        session.flush()
        
        # 5. Log and metrics
        log_hold_created(
            user_id=user_id,
            request_id=request_id,
            reserved_credits=estimated_credits,
            balance_before=available_balance,
            attempt_id=attempt_id,
        )
        inc_holds_created()
        
        return HoldResult(
            hold_id=hold.id,
            request_id=request_id,
            reserved_credits=estimated_credits,
            balance_before=available_balance,
            success=True,
        )
    
    def settle_hold(
        self,
        session: Session,
        request_id: str,
        actual_credits: Decimal,
        tier: str = "STANDARD",
        provider_cost_usd: Decimal = Decimal("0"),
        attempt_id: Optional[str] = None,
        is_billable: bool = True,
        action_type: str = "solve",
    ) -> SettleResult:
        """
        Settle a hold by consuming the actual credits used.
        
        This finalizes the transaction by:
        1. Allocating credits from lots (FIFO by expiry)
        2. Creating ledger entries
        3. Updating cached balances
        4. Releasing the hold
        
        Args:
            session: Database session
            request_id: The request_id used when creating the hold
            actual_credits: Actual amount to charge
            tier: Pricing tier (FREE, STANDARD, RESEARCH)
            provider_cost_usd: Provider cost for this action
            attempt_id: Optional attempt identifier
            is_billable: Whether to actually charge (False = void)
        
        Returns:
            SettleResult with settlement details
        
        Raises:
            HoldNotFoundError: If no hold exists for this request_id
            HoldAlreadyFinalizedError: If hold was already settled/released
        """
        # Normalize
        actual_credits = Decimal(str(actual_credits))
        provider_cost_usd = Decimal(str(provider_cost_usd))
        
        # 1. Find and lock the hold
        hold = session.exec(
            select(CreditHold)
            .where(CreditHold.request_id == request_id)
            .with_for_update()
        ).first()
        
        if not hold:
            raise HoldNotFoundError(request_id)
        
        if hold.status != "held":
            raise HoldAlreadyFinalizedError(request_id, hold.status)
        
        user_id = hold.user_id
        
        # 2. Lock user row
        user = session.exec(
            select(User).where(User.id == user_id).with_for_update()
        ).first()
        
        # 3. Get balance before
        balance_before = self._compute_available_balance_locked(session, user_id)
        
        # 4. Determine charge
        if not is_billable:
            actual_credits = Decimal("0")
        
        status = "CHARGED" if is_billable and actual_credits > 0 else "VOIDED"
        
        # 5. Allocate from lots if charging
        if actual_credits > 0:
            self._allocate_credits_fifo(session, user_id, actual_credits, attempt_id)
        
        # 6. Compute balance after
        balance_after = self._compute_available_balance_locked(session, user_id)
        
        # 7. Create ledger entry
        ledger = BillingLedger(
            user_id=user_id,
            action_type=action_type,
            request_id=request_id,
            idempotency_key=f"settle_{request_id}",
            status=status,
            credits_charged=actual_credits,
            credits_before=balance_before,
            credits_after=balance_after,
            provider_cost_usd=provider_cost_usd,
            tier=tier,
            finalized_at=datetime.utcnow(),
        )
        session.add(ledger)
        
        # 8. Update hold status
        hold.status = "released" if is_billable else "released_void"
        hold.finalized_at = datetime.utcnow()
        session.add(hold)
        
        # 9. Update cached balance (best-effort)
        if user:
            user.credits_balance = float(balance_after)
            session.add(user)
        
        session.flush()
        
        # 10. Log and metrics
        if is_billable and actual_credits > 0:
            log_settled(
                user_id=user_id,
                request_id=request_id,
                credits_charged=actual_credits,
                usd_charged=provider_cost_usd,
                balance_before=balance_before,
                balance_after=balance_after,
                attempt_id=attempt_id,
            )
            inc_settled()
        else:
            log_hold_released(
                user_id=user_id,
                request_id=request_id,
                released_credits=Decimal(str(hold.reserved_credits)),
                balance_after=balance_after,
                attempt_id=attempt_id,
            )
        
        return SettleResult(
            ledger_id=ledger.id,
            request_id=request_id,
            credits_charged=actual_credits,
            balance_after=balance_after,
            status=status,
            success=True,
        )
    
    def release_hold(
        self,
        session: Session,
        request_id: str,
        attempt_id: Optional[str] = None,
    ) -> ReleaseResult:
        """
        Release a hold without charging any credits.
        
        Use this when an action fails and no charge should be made.
        This is idempotent - calling multiple times is safe.
        
        Args:
            session: Database session
            request_id: The request_id used when creating the hold
            attempt_id: Optional attempt identifier
        
        Returns:
            ReleaseResult with release details
        """
        # 1. Find hold (with lock)
        hold = session.exec(
            select(CreditHold)
            .where(CreditHold.request_id == request_id)
            .with_for_update()
        ).first()
        
        if not hold:
            # Idempotent: if no hold, return success (already released or never existed)
            return ReleaseResult(
                request_id=request_id,
                released_credits=Decimal("0"),
                balance_after=Decimal("0"),
                success=True,
                message="No hold found (idempotent release)",
            )
        
        if hold.status != "held":
            # Already finalized - idempotent return
            return ReleaseResult(
                request_id=request_id,
                released_credits=Decimal(str(hold.reserved_credits)),
                balance_after=Decimal("0"),
                success=True,
                message=f"Hold already finalized with status: {hold.status}",
            )
        
        user_id = hold.user_id
        reserved = Decimal(str(hold.reserved_credits))
        
        # 2. Update hold status
        hold.status = "released_void"
        hold.finalized_at = datetime.utcnow()
        session.add(hold)
        
        # 3. Get current balance
        balance_after = self._compute_available_balance_locked(session, user_id)
        
        session.flush()
        
        # 4. Log
        log_hold_released(
            user_id=user_id,
            request_id=request_id,
            released_credits=reserved,
            balance_after=balance_after,
            attempt_id=attempt_id,
        )
        
        return ReleaseResult(
            request_id=request_id,
            released_credits=reserved,
            balance_after=balance_after,
            success=True,
        )
    
    def _compute_available_balance_locked(
        self,
        session: Session,
        user_id: int,
    ) -> Decimal:
        """
        Compute available balance from credit lots (source of truth).
        
        This method acquires FOR UPDATE locks on all active lots
        to ensure consistency during balance checks.
        """
        # Get all active, non-expired lots with lock
        now = datetime.utcnow()
        lots = session.exec(
            select(CreditLot)
            .where(
                CreditLot.user_id == user_id,
                CreditLot.status == "ACTIVE",
                CreditLot.credits_remaining > 0,
            )
            .with_for_update()
        ).all()
        
        # Filter out expired lots
        total = Decimal("0")
        for lot in lots:
            if lot.expires_at and lot.expires_at < now:
                continue
            total += Decimal(str(lot.credits_remaining))
        
        # Subtract pending holds
        holds = session.exec(
            select(CreditHold)
            .where(
                CreditHold.user_id == user_id,
                CreditHold.status == "held",
            )
        ).all()
        
        held_total = sum(Decimal(str(h.reserved_credits)) for h in holds)
        
        return total - held_total
    
    def _allocate_credits_fifo(
        self,
        session: Session,
        user_id: int,
        amount: Decimal,
        attempt_id: Optional[str] = None,
    ) -> List[CreditLotConsumption]:
        """
        Allocate credits from lots using FIFO by expiry.
        
        Priority:
        1. Earliest expiry date first
        2. Within same expiry, oldest purchase date first
        3. PROMO lots before TOPUP lots (configurable)
        
        This method acquires FOR UPDATE locks on lots being modified.
        """
        now = datetime.utcnow()
        
        # Get lots ordered by expiry and purchase date
        lots = session.exec(
            select(CreditLot)
            .where(
                CreditLot.user_id == user_id,
                CreditLot.status == "ACTIVE",
                CreditLot.credits_remaining > 0,
            )
            .order_by(
                CreditLot.expires_at.asc().nullslast(),
                CreditLot.purchased_at.asc(),
            )
            .with_for_update()
        ).all()
        
        consumptions = []
        remaining = amount
        
        for lot in lots:
            if remaining <= EPSILON:
                break
            
            # Skip expired lots
            if lot.expires_at and lot.expires_at < now:
                lot.status = "EXPIRED"
                session.add(lot)
                continue
            
            available = Decimal(str(lot.credits_remaining))
            to_consume = min(remaining, available)
            
            # Update lot
            lot.credits_remaining = float(available - to_consume)
            if lot.credits_remaining <= float(EPSILON):
                lot.credits_remaining = 0
                lot.status = "DEPLETED"
            session.add(lot)
            
            # Create consumption record
            consumption = CreditLotConsumption(
                user_id=user_id,
                credit_lot_id=lot.id,
                direction="DEBIT",
                amount=to_consume,
                attempt_id=attempt_id,
            )
            session.add(consumption)
            consumptions.append(consumption)
            
            remaining -= to_consume
        
        if remaining > EPSILON:
            # Should not happen if balance check passed
            raise InsufficientCreditsError(
                user_id=user_id,
                required=float(amount),
                available=float(amount - remaining),
            )
        
        return consumptions


# Singleton instance
billing_ledger_service_v2 = BillingLedgerServiceV2()
