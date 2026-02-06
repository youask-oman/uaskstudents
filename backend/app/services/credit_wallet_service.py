from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select, func, and_

from app.models import CreditLot, User, BillingLedger
# Import Allocator if possible/avoid circular
from app.services.credit_lot_allocator import credit_lot_allocator

class CreditWalletService:
    def get_balance(self, session: Session, user_id: int) -> float:
        """
        Calculate total valid (non-expired) credits for a user.
        Uses Phase 2 logic: Sum of Active Lots.
        """
        now = datetime.utcnow()
        statement = select(func.sum(CreditLot.credits_remaining)).where(
            CreditLot.user_id == user_id,
            CreditLot.status == 'ACTIVE',
            CreditLot.credits_remaining > 0,
            # Handling None expires_at as "Never expires" (valid)
            # or expires_at > now
            (CreditLot.expires_at == None) | (CreditLot.expires_at > now)
        )
        result = session.exec(statement).one()
        return float(result) if result else 0.0

    def add_credits(
        self, 
        session: Session, 
        user_id: int, 
        amount: float, 
        source: str, 
        expiry_days: int = 120,
        lot_type: str = "TOPUP",
        external_ref: Optional[str] = None
    ) -> CreditLot:
        """
        Add a new batch of credits to the user's wallet.
        """
        from datetime import timedelta
        # If expiry_days is 0 or very large, treat as infinite? 
        # Default 120.
        expires_at = None
        if expiry_days:
             expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        lot = CreditLot(
            user_id=user_id,
            credits_total=amount,
            credits_remaining=amount,
            expires_at=expires_at,
            source=source,
            lot_type=lot_type,
            status="ACTIVE",
            external_ref=external_ref
        )
        session.add(lot)
        session.flush()
        return lot

    def deduct_credits(
        self, 
        session: Session, 
        user_id: int, 
        amount: float, 
        reference_id: Optional[str] = None,
        meta: Optional[dict] = None
    ) -> bool:
        """
        Deduct credits:
        1. Create UsageLedger (DEBIT).
        2. Update Subscription Balance (Sync).
        3. Allocate against Lots via FIFO (Phase 2).
        """
        if amount <= 0:
            return True

        # 1. Get User/Subscription
        # We need subscription for UsageLedger
        user = session.get(User, user_id)
        # Handle lazy loading or missing sub?
        if not user:
            raise ValueError("User not found")
        
        sub = user.subscription
        # If no subscription, we can't create UsageLedger (requires sub_id).
        # In this system, every user should have a sub (Free).
        if not sub:
             from app.services.subscription_service import subscription_service
             sub = subscription_service.get_or_create_subscription(session, user)

        # 2. Check Balance (Phase 2: Check Lots vs Subscription?)
        # Subscription.credits_balance should be the cache.
        if sub.credits_balance < amount:
             # Double check against lots?
             real_balance = self.get_balance(session, user_id)
             if real_balance < amount:
                  raise ValueError(f"Insufficient credits. Required: {amount}, Available: {real_balance}")

        # 3. Create UsageLedger
        from app.models import UsageLedger # Import inside to avoid circular if any
        ledger_entry = UsageLedger(
            subscription_id=sub.id,
            transaction_type="DEBIT",
            amount=amount,
            # Balance after prediction
            balance_after=sub.credits_balance - amount,
            reference_id=reference_id,
            meta=meta
        )
        session.add(ledger_entry)
        session.flush() # Get ID
        
        # 4. Update Subscription
        sub.credits_balance -= amount
        sub.credits_used_this_period += amount
        session.add(sub)
        
        # 5. FIFO Allocation (Phase 2)
        try:
             credit_lot_allocator.consume_credits(
                 session, 
                 user_id, 
                 amount, 
                 usage_ledger_id=ledger_entry.id
             )
             return True
        except Exception as e:
             raise e

credit_wallet_service = CreditWalletService()
