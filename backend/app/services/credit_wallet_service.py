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
        Respects 'overage_policy' if set to 'block'.
        """
        from app.models import Subscription
        
        # 1. Determine Overage Policy
        sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
        overage_policy = "paygo"
        if sub and sub.plan:
            overage_policy = (sub.plan.features or {}).get("overage_policy", "paygo")
            
        now = datetime.utcnow()
        statement = select(func.sum(CreditLot.credits_remaining)).where(
            CreditLot.user_id == user_id,
            CreditLot.status == 'ACTIVE',
            CreditLot.credits_remaining > 0,
            (CreditLot.expires_at == None) | (CreditLot.expires_at > now)
        )
        
        if overage_policy == "block":
            # Strict limit: only count subscription grants
            statement = statement.where(CreditLot.lot_type == "SUBSCRIPTION_GRANT")
            
        result = session.exec(statement).one()
        return float(result) if result else 0.0

    def add_credits(
        self, 
        session: Session, 
        user_id: int, 
        amount: float, 
        source: str, 
        expiry_days: Optional[int] = 120,
        expires_at: Optional[datetime] = None,
        lot_type: str = "TOPUP",
        external_ref: Optional[str] = None
    ) -> CreditLot:
        """
        Add a new batch of credits to the user's wallet.
        """
        from datetime import timedelta
        from decimal import Decimal
        
        amount_dec = Decimal(str(amount))
        final_expires_at = expires_at
        if final_expires_at is None and expiry_days:
             final_expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        lot = CreditLot(
            user_id=user_id,
            credits_total=amount_dec,
            credits_remaining=amount_dec,
            expires_at=final_expires_at,
            source=source,
            lot_type=lot_type,
            status="ACTIVE",
            external_ref=external_ref
        )
        session.add(lot)
        session.flush()
        
        # Sync Subscription Balance
        user = session.get(User, user_id)
        if user and user.subscription:
            from app.models import UsageLedger
            
            sub = user.subscription
            sub.credits_balance += amount_dec
            
            # Create Audit Entry
            ledger_entry = UsageLedger(
                subscription_id=sub.id,
                transaction_type="CREDIT",
                amount=amount_dec,
                balance_after=sub.credits_balance,
                reference_id=external_ref,
                meta={"source": source, "lot_type": lot_type}
            )
            session.add(ledger_entry)
            session.add(sub)
            
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
        1. Check Balance (respecting overage_policy).
        2. Allocate against Lots via FIFO (respecting overage_policy).
        3. Create UsageLedger (DEBIT).
        4. Update Subscription Balance.
        """
        if amount <= 0:
            return True

        # 1. Get User/Subscription
        user = session.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        
        sub = user.subscription
        if not sub:
             from app.services.subscription_service import subscription_service
             sub = subscription_service.get_or_create_subscription(session, user)

        # 2. Check USABLE Balance (this already respects 'block')
        usable_balance = self.get_balance(session, user_id)
        if usable_balance < amount:
             raise ValueError(f"Insufficient credits. Required: {amount}, Usable Available: {usable_balance}")

        # 3. Create UsageLedger
        from app.models import UsageLedger
        ledger_entry = UsageLedger(
            subscription_id=sub.id,
            transaction_type="DEBIT",
            amount=amount,
            balance_after=sub.credits_balance - amount,
            reference_id=reference_id,
            meta=meta
        )
        session.add(ledger_entry)
        session.flush()
        
        # 4. Update Subscription Cache
        sub.credits_balance -= amount
        sub.credits_used_this_period += amount
        session.add(sub)
        
        # 5. FIFO Allocation (Consumes from Lots)
        try:
             consumptions = credit_lot_allocator.consume_credits(
                 session, 
                 user_id, 
                 amount, 
                 usage_ledger_id=ledger_entry.id,
                 subscription_id=sub.id
             )
             
             # Verify total consumption matches request
             total_consumed = sum(c.amount for c in consumptions)
             if total_consumed < (amount - 0.0001):
                  # This should not happen if get_balance check passed
                  raise ValueError(f"Allocation failure: only consumed {total_consumed}/{amount}")
                  
             return True
        except Exception as e:
             raise e

credit_wallet_service = CreditWalletService()
