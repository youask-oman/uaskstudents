import sys
import os
from datetime import datetime, timedelta
from sqlmodel import Session, select, func
from sqlalchemy import text

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import User, Subscription, Plan, CreditLot, SubscriptionPeriod, UsageLedger, CreditLotConsumption
from app.services.credit_wallet_service import credit_wallet_service
from app.jobs.grant_subscription_credits_job import run_grant_job

def demo_drilldown_and_rollover():
    print("=== Phase 3 Subscription Demo: Drilldown & Rollover ===")
    
    with Session(engine) as session:
        # 1. Setup specific test user
        email = "demo_p3_qa@test.com"
        user = session.exec(select(User).where(User.email == email)).first()
        if user:
            # Cleanup old data for clean demo
            print(f"Cleaning up old data for {email}...")
            session.exec(text(f"DELETE FROM creditlotconsumption WHERE user_id = {user.id}"))
            session.exec(text(f"DELETE FROM usageledger WHERE subscription_id IN (SELECT id FROM subscription WHERE user_id = {user.id})"))
            session.exec(text(f"DELETE FROM creditlot WHERE user_id = {user.id}"))
            session.exec(text(f"DELETE FROM subscriptionperiod WHERE subscription_id IN (SELECT id FROM subscription WHERE user_id = {user.id})"))
            session.exec(text(f"DELETE FROM subscription WHERE user_id = {user.id}"))
            session.delete(user)
            session.commit()

        user = User(email=email, full_name="QA Demo User", password_hash="x")
        session.add(user)
        session.commit()
        
        # Ensure Plan exists
        plan = session.exec(select(Plan).where(Plan.slug == "standard")).first()
        if not plan:
            plan = Plan(
                slug="standard", name="Standard", credits_per_month=100, 
                price_monthly_cents=1000, price_yearly_cents=10000,
                features={"monthly_credits_included": 100, "overage_policy": "paygo", "spend_order": "allowance_first"}
            )
            session.add(plan)
            session.commit()
            
        sub = Subscription(
            user_id=user.id, plan_id=plan.id, status="active", 
            current_period_start=datetime.utcnow() - timedelta(days=5),
            current_period_end=datetime.utcnow() + timedelta(days=25),
            credits_balance=0.0
        )
        session.add(sub)
        session.commit()
        
        print(f"Setup User ID: {user.id}, Sub ID: {sub.id}")

        # --- PART 1: DRILLDOWN (Grant then Topup) ---
        print("\n--- Testing Drilldown: Grant then Topup ---")
        # Add Grant
        grant_lot = credit_wallet_service.add_credits(
            session, user.id, amount=50.0, lot_type="SUBSCRIPTION_GRANT", source="GRANT_DEMO"
        )
        # Add Topup
        topup_lot = credit_wallet_service.add_credits(
            session, user.id, amount=100.0, lot_type="TOPUP", source="PAYMENT_DEMO"
        )
        session.commit()
        
        print(f"Added Grant: {grant_lot.credits_total} cr, Topup: {topup_lot.credits_total} cr")
        print(f"Current Balance: {credit_wallet_service.get_balance(session, user.id)} cr")
        
        # Deduct 70 credits
        print("Deducting 70 credits (Should use 50 from Grant, 20 from Topup)...")
        credit_wallet_service.deduct_credits(session, user.id, 70.0, reference_id="demo_drilldown")
        session.commit()
        
        # Verify Consumptions
        consumptions = session.exec(select(CreditLotConsumption).where(CreditLotConsumption.user_id == user.id)).all()
        print(f"Found {len(consumptions)} consumption records:")
        for c in consumptions:
            lot = session.get(CreditLot, c.credit_lot_id)
            print(f" - Amount: {c.amount}, Lot Type: {lot.lot_type}, Lot ID: {lot.id}")

        # Check final balance
        session.refresh(sub)
        print(f"Final Sub Balance Cache: {sub.credits_balance} cr")
        
        # --- PART 2: ROLLOVER (Grant created once, not twice) ---
        print("\n--- Testing Rollover: Idempotent Grant ---")
        # Force period end
        sub.current_period_end = datetime.utcnow() - timedelta(minutes=1)
        session.add(sub)
        session.commit()
        
        print(f"Forced Period End for Sub {sub.id}: {sub.current_period_end}")
        
        # Run Grant Job (1st time)
        print("Running Grant Job (1st time)...")
        count1 = run_grant_job(session)
        session.commit()
        print(f"Grant Job 1: Processed {count1} subscriptions.")
        
        # Verify Period & Lot
        periods = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).all()
        print(f"Period count after Job 1: {len(periods)}")
        for p in periods:
            print(f" - Period ID: {p.id}, Status: {p.status}, Grant: {p.granted_credits}")
            
        # Run Grant Job (2nd time) - Should be IDEMPOTENT
        print("Running Grant Job (2nd time)...")
        count2 = run_grant_job(session)
        session.commit()
        print(f"Grant Job 2: Processed {count2} subscriptions.")
        
        # Verify no extra periods/lots
        periods_final = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).all()
        print(f"Period count after Job 2: {len(periods_final)}")
        
        if len(periods_final) == len(periods):
            print("SUCCESS: Rollover is idempotent (Grant created once).")
        else:
            print("FAILURE: Rollover created duplicate grants!")

    print("\nDemo Complete.")

if __name__ == "__main__":
    from sqlalchemy import text
    demo_drilldown_and_rollover()
