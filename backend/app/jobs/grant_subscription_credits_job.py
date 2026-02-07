
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from sqlmodel import Session, select, desc

from app.database import get_session
from app.models import Subscription, SubscriptionPeriod, Plan, CreditLot, UsageLedger, User
from app.services.credit_wallet_service import credit_wallet_service

logger = logging.getLogger(__name__)

def run_grant_job(session: Session):
    """
    Core logic to grant monthly subscription credits.
    Idempotent: Checks for existence of SubscriptionPeriod before granting.
    """
    logger.info("Starting Subscription Grant Job...")
    
    # 1. Find Active Subscriptions
    # We want active subscriptions where today falls within a period that hasn't been granted yet.
    # Actually, we rely on 'current_period_start'. If that date is passed, we should have a period for it.
    
    now = datetime.utcnow()
    
    subs = session.exec(
        select(Subscription).where(Subscription.status == "active")
    ).all()
    
    granted_count = 0
    errors = 0
    
    for sub in subs:
        try:
            # Check if period needs rolling over?
            # Phase 3 spec says "make subscription benefits real".
            # Assuming external system handles billing/period rollover timestamps, 
            # OR we handle simple rollover here if dates are old.
            
            # Simple Rollover Logic (if needed):
            if sub.current_period_end < now:
                # It's expired or needs renewal.
                if sub.auto_renew:
                    # Advance period
                    # This is simple monthly logic.
                    logger.info(f"Advancing period for sub {sub.id}")
                    sub.current_period_start = sub.current_period_end
                    sub.current_period_end = sub.current_period_end + timedelta(days=30)
                    session.add(sub)
                    session.commit()
                    session.refresh(sub)
                else:
                    # Expired
                    sub.status = "expired"
                    session.add(sub)
                    session.commit()
                    continue

            # Target Period
            p_start = sub.current_period_start
            p_end = sub.current_period_end
            
            # 2. Check overlap/existence
            existing_period = session.exec(
                select(SubscriptionPeriod)
                .where(SubscriptionPeriod.subscription_id == sub.id)
                .where(SubscriptionPeriod.period_start == p_start)
            ).first()
            
            if existing_period:
                # Already granted for this period
                continue
                
            # 3. Create Period & Grant
            logger.info(f"Granting credits for sub {sub.id} (Period: {p_start})")
            
            # Get Plan Config
            plan = sub.plan
            if not plan:
                logger.error(f"Subscription {sub.id} has no plan")
                continue
                
            features = plan.features or {}
            credits_to_grant = float(features.get("monthly_credits_included", 0))
            
            # Create Lot
            lot_id = None
            if credits_to_grant > 0:
                lot = credit_wallet_service.add_credits(
                    session,
                    user_id=sub.user_id,
                    amount=credits_to_grant,
                    source="SUBSCRIPTION_GRANT",
                    external_ref=f"sub_{sub.id}_{p_start.isoformat()}",
                    expires_at=p_end
                )
                # Ensure lot_type is correct (service defaults to TOPUP mostly, let's update it)
                lot.lot_type = "SUBSCRIPTION_GRANT"
                lot.subscription_id = sub.id
                session.add(lot)
                session.flush()
                lot_id = lot.id
            
            # Reset Usage Counters
            sub.feature_usage = {}
            # Create Reset Audit Entry
            from app.models import UsageLedger
            reset_entry = UsageLedger(
                subscription_id=sub.id,
                transaction_type="RESET",
                amount=0,
                balance_after=sub.credits_balance, # This balance was just updated by add_credits
                meta={"reason": "MONTHLY_ROLLOVER", "period_start": p_start.isoformat()}
            )
            session.add(reset_entry)
            
            # Create SubscriptionPeriod
            period = SubscriptionPeriod(
                subscription_id=sub.id,
                period_start=p_start,
                period_end=p_end,
                status="OPEN",
                granted_credits=int(credits_to_grant),
                grant_lot_id=lot_id
            )
            session.add(period)
            session.add(sub) # Save Reset counters
            
            session.commit()
            granted_count += 1
            
        except Exception as e:
            logger.error(f"Error processing sub {sub.id}: {e}")
            errors += 1
            session.rollback()
            
    logger.info(f"Grant Job Complete. Granted: {granted_count}, Errors: {errors}")
    return granted_count

if __name__ == "__main__":
    # Local Test Run
    from app.database import engine
    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        run_grant_job(session)
