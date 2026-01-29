
from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select, func, and_

from app.models import CreditLot, User

class CreditWalletService:
    def get_balance(self, session: Session, user_id: int) -> float:
        """
        Calculate total valid (non-expired) credits for a user.
        """
        now = datetime.utcnow()
        statement = select(func.sum(CreditLot.credits_remaining)).where(
            CreditLot.user_id == user_id,
            CreditLot.is_active == True,
            CreditLot.credits_remaining > 0,
            CreditLot.expires_at > now
        )
        result = session.exec(statement).one()
        return float(result) if result else 0.0

    def add_credits(
        self, 
        session: Session, 
        user_id: int, 
        amount: float, 
        source: str, 
        expiry_days: int = 120
    ) -> CreditLot:
        """
        Add a new batch of credits to the user's wallet.
        """
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        lot = CreditLot(
            user_id=user_id,
            credits_total=amount,
            credits_remaining=amount,
            expires_at=expires_at,
            source=source,
            is_active=True
        )
        session.add(lot)
        session.commit()
        session.refresh(lot)
        return lot

    def deduct_credits(self, session: Session, user_id: int, amount: float) -> bool:
        """
        Deduct credits using FIFO strategy (oldest expiring first).
        Returns True if successful, False if insufficient funds (atomic check).
        Raises ValueError if insufficient funds.
        """
        if amount <= 0:
            return True

        # Check total balance first
        current_balance = self.get_balance(session, user_id)
        if current_balance < amount:
            raise ValueError(f"Insufficient credits. Required: {amount}, Available: {current_balance}")

        # Fetch active lots ordered by purchase date (FIFO)
        # Note: We prioritize primarily by expiry? Or purchase date?
        # Usually FIFO means purchase date. But we want to spend correctly.
        # Let's order by purchased_at ASC.
        now = datetime.utcnow()
        statement = select(CreditLot).where(
            CreditLot.user_id == user_id,
            CreditLot.is_active == True,
            CreditLot.credits_remaining > 0,
            CreditLot.expires_at > now
        ).order_by(CreditLot.purchased_at.asc())
        
        lots = session.exec(statement).all()
        
        remaining_to_deduct = amount
        
        for lot in lots:
            if remaining_to_deduct <= 0:
                break
                
            deduct_from_lot = min(lot.credits_remaining, remaining_to_deduct)
            
            lot.credits_remaining -= deduct_from_lot
            remaining_to_deduct -= deduct_from_lot
            session.add(lot)
            
        if remaining_to_deduct > 0.0001: # Float epsilon check
            # Should have been caught by initial balance check, but handled for safety
            session.rollback()
            raise ValueError("Concurrency error: Balance changed during deduction.")
            
        session.commit()
        return True

credit_wallet_service = CreditWalletService()
