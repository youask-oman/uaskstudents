
from datetime import datetime
import logging
from sqlmodel import Session, select

from app.database import engine
from app.models import SubscriptionPeriod, CreditLot

logger = logging.getLogger(__name__)

def run_expiry_job(session: Session):
    """
    Closes past subscription periods and voids leftover grant credits.
    """
    logger.info("Starting Subscription Expiry Job...")
    
    now = datetime.utcnow()
    
    # Find active periods that have ended
    periods = session.exec(
        select(SubscriptionPeriod)
        .where(SubscriptionPeriod.status == "OPEN")
        .where(SubscriptionPeriod.period_end < now)
    ).all()
    
    expired_count = 0
    errors = 0
    
    for period in periods:
        try:
            logger.info(f"Closing period {period.id} (Ended: {period.period_end})")
            
            # 1. Expire Associated Lot
            if period.grant_lot_id:
                lot = session.get(CreditLot, period.grant_lot_id)
                if lot and lot.status == "ACTIVE":
                    remaining = lot.credits_remaining
                    lot.status = "EXPIRED"
                    lot.credits_remaining = 0 # Enforce 0 balance visually
                    session.add(lot)
                    
                    # Update Subscription Balance Cache
                    sub = period.subscription
                    if sub:
                        from app.models import UsageLedger
                        sub.credits_balance = max(0, sub.credits_balance - remaining)
                        
                        # Audit entry
                        ledger_entry = UsageLedger(
                            subscription_id=sub.id,
                            transaction_type="DEBIT",
                            amount=remaining,
                            balance_after=sub.credits_balance,
                            reference_id=f"expire_{lot.id}",
                            meta={"reason": "EXPIRY", "lot_id": lot.id}
                        )
                        session.add(ledger_entry)
                        session.add(sub)
            
            # 2. Close Period
            period.status = "CLOSED"
            session.add(period)
            
            session.commit()
            expired_count += 1
            
        except Exception as e:
            logger.error(f"Error expiring period {period.id}: {e}")
            errors += 1
            session.rollback()
            
    logger.info(f"Expiry Job Complete. Expired: {expired_count}, Errors: {errors}")
    return expired_count

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        run_expiry_job(session)
