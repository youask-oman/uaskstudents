
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from sqlmodel import Session, select, func
from sqlalchemy import desc
# Removed credit_wallet_service import to fix circular dependency
from app.models import CreditLot, CreditLotConsumption, Subscription, User

class CreditLotAllocator:
    """
    Manages FIFO consumption of credits across lots.
    """
    
    def consume_credits(
        self, 
        session: Session, 
        user_id: int, 
        amount_needed: float, 
        usage_ledger_id: int,
        subscription_id: Optional[int] = None
    ) -> List[CreditLotConsumption]:
        """
        Consumes credits utilizing FIFO strategy (Expires soonest -> Oldest purchase).
        Creates Consumption records and updates Lot balances.
        Does NOT update Subscription balance (caller responsibility or handled legacy).
        """
        if amount_needed <= 0:
            return []
            
        # 1. Select Eligible Lots
        query = select(CreditLot).where(
            CreditLot.user_id == user_id,
            CreditLot.credits_remaining > 0,
            CreditLot.status == 'ACTIVE'
        ).order_by(
            # Sort by Expiry ASC (Non-Null first? No, standard logic usually Null=Never expires=Last)
            # SQLite/PG handles nulls differently. Let's explicitly sort.
            # Usually we want: Expiring soonest (e.g. tomorrow) FIRST.
            # Never expiring LAST.
            # So standard ASC works for dates.
            # What about NULL? NULL > Date? 
            # In PG: NULLS LAST is good. In SQLModel/SA we can specify.
        ).order_by(
           CreditLot.expires_at.asc().nullslast(), # Consume expiring logic first
           CreditLot.purchased_at.asc(),           # Then Oldest
           CreditLot.id.asc()
        )
        
        lots = session.exec(query).all()
        
        consumptions = []
        remaining_to_deduct = amount_needed
        
        for lot in lots:
            if remaining_to_deduct <= 0:
                break
                
            # Check expiry (Double check dynamic expiry)
            if lot.expires_at and lot.expires_at < datetime.utcnow():
                lot.status = 'EXPIRED'
                lot.credits_remaining = 0 # Wipe expired
                session.add(lot)
                continue
                
            available = lot.credits_remaining
            to_take = min(available, remaining_to_deduct)
            
            # Update Lot
            lot.credits_remaining -= to_take
            if lot.credits_remaining <= 0.0001: # Float epsilon safe
                lot.credits_remaining = 0.0
                lot.status = 'DEPLETED'
            
            session.add(lot)
            
            # Create Consumption Record
            consumption = CreditLotConsumption(
                user_id=user_id,
                subscription_id=subscription_id or lot.subscription_id,
                credit_lot_id=lot.id,
                usage_ledger_id=usage_ledger_id,
                direction="DEBIT",
                amount=to_take
            )
            session.add(consumption)
            consumptions.append(consumption)
            
            remaining_to_deduct -= to_take
        
        # If still remaining, we have a "Leak" (Balance > Lots).
        # We record it as untracked consumption if needed, or just let it slide (Legacy Balance).
        # We assume caller checked total balance availability via Subscription.
        
        return consumptions

    def refund_credits(
        self,
        session: Session,
        usage_ledger_id: int
    ) -> List[CreditLotConsumption]:
        """
        Restores credits to the lots that funded the usage.
        """
        # Find original consumptions
        orig_consumptions = session.exec(
            select(CreditLotConsumption).where(
                CreditLotConsumption.usage_ledger_id == usage_ledger_id,
                CreditLotConsumption.direction == "DEBIT"
            )
        ).all()
        
        refunds = []
        for c in orig_consumptions:
            lot = session.get(CreditLot, c.credit_lot_id)
            if not lot:
                # Lot deleted? fallback or log warning
                continue
                
            # Restore
            # Check if lot was depleted/expired.
            # If expired, do we refund? Policy says "refund to newest unexpired".
            # But simpler: Restore to origin. If origin is EXPIRED, it stays EXPIRED or we revive?
            # User Policy: "refund to newest unexpired lot" if simplest.
            # Implementation: Let's try restore to origin first. If origin expired -> Move to newest.
            
            target_lot = lot
            if lot.status == 'EXPIRED' or (lot.expires_at and lot.expires_at < datetime.utcnow()):
                # Find newest active
                newest = session.exec(select(CreditLot).where(
                    CreditLot.user_id == c.user_id, CreditLot.status == 'ACTIVE'
                ).order_by(CreditLot.created_at.desc())).first()
                if newest:
                    target_lot = newest
                else:
                    # Create Migration Lot? or Just revive legacy balance?
                    # Minimal: Just fail lot restore, but User balance updates anyway via CreditWalletService
                    continue
            
            target_lot.credits_remaining += c.amount
            if target_lot.credits_remaining > 0 and target_lot.status == 'DEPLETED':
                 target_lot.status = 'ACTIVE'
            
            session.add(target_lot)
            
            refund = CreditLotConsumption(
                user_id=target_lot.user_id,
                credit_lot_id=target_lot.id,
                usage_ledger_id=usage_ledger_id,
                direction="REFUND",
                amount=c.amount
            )
            session.add(refund)
            refunds.append(refund)
            
        return refunds

credit_lot_allocator = CreditLotAllocator()
