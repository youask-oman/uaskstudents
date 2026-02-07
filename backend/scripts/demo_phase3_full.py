
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.database import engine
from app.models import User, Subscription, Plan, CreditLot, UsageLedger, SubscriptionPeriod, CreditLotConsumption
from app.services.credit_lot_allocator import credit_lot_allocator
from app.jobs.grant_subscription_credits_job import run_grant_job
from app.jobs.expire_subscription_grants_job import run_expiry_job

def run_demo():
    print("=== Phase 3 Drilldown & Rollover Demo ===")
    
    with Session(engine) as session:
        # Pre-cleanup (optional)
        email = "demo_phase3@example.com"
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            # Clean up user specific data if needed, or just reuse
            # For clean demo, let's delete user and related
            print(f"Cleaning up previous run for {email}...")
            # Naive cleanup, cascading might not be set up on everything
            # Let's just make a unique email each run
            pass
            
        import uuid
        unique_email = f"demo_p3_{str(uuid.uuid4())[:8]}@example.com"
        print(f"Creating User: {unique_email}")
        
        # 1. Create User & Plan
        user = User(email=unique_email, full_name="Demo User", password_hash="x", role="student")
        session.add(user)
        session.commit()
        
        plan = session.exec(select(Plan).where(Plan.slug == "standard")).first()
        if not plan:
            print("Standard plan not found, seeding...")
            plan = Plan(slug="standard", name="Std", credits_per_month=300, price_monthly_cents=1000, price_yearly_cents=10000,
                        features={"monthly_credits_included": 300, "overage_policy": "paygo", "spend_order": "allowance_first"})
            session.add(plan)
            session.commit()

        # 2. Create Active Subscription (Start today)
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            credits_balance=0.0
        )
        session.add(sub)
        session.commit()
        print(f"Subscription Created: ID {sub.id}")
        
        # 3. Trigger Grant Job (Should create GRANT lot)
        print("\n--- Running Grant Job (Initial) ---")
        run_grant_job(session)
        
        session.refresh(sub)
        p1 = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).first()
        print(f"Period 1 Created: ID {p1.id}, Status: {p1.status}, Granted: {p1.granted_credits}")
        
        # Verify Grant Lot
        grant_lot = session.get(CreditLot, p1.grant_lot_id)
        if not grant_lot:
             print("ERROR: Grant lot missing!")
             return
        print(f"Grant Lot: ID {grant_lot.id}, Type: {grant_lot.lot_type}, Balance: {grant_lot.credits_remaining}")
        
        # 4. Add TOPUP Lot (PayGo)
        print("\n--- Adding Top-Up Lot ---")
        topup_lot = CreditLot(
            user_id=user.id, credits_total=50.0, credits_remaining=50.0,
            lot_type="TOPUP", status="ACTIVE", source="MANUAL",
            purchased_at=datetime.utcnow(), expires_at=None
        )
        session.add(topup_lot)
        session.commit()
        print(f"TopUp Lot Created: ID {topup_lot.id}, Balance: {topup_lot.credits_remaining}")
        
        # 5. Consumption Drilldown
        # Scenario: User needs 320 credits.
        # User has: 300 (Grant) + 50 (TopUp) = 350 Total.
        # Expect: 300 from Grant, 20 from TopUp.
        print("\n--- Executing Debit of 320.0 Credits ---")
        
        ledger = UsageLedger(
            subscription_id=sub.id, transaction_type="DEBIT", amount=320.0, 
            balance_after=0, reference_id="drilldown_demo_1"
        )
        session.add(ledger)
        session.flush()
        
        consumptions = credit_lot_allocator.consume_credits(
            session, user.id, 320.0, ledger.id, sub.id
        )
        session.commit()
        
        print("Debit Successful.")
        print("\n--- Consumption Drilldown ---")
        for c in consumptions:
            lot = session.get(CreditLot, c.credit_lot_id)
            print(f"Lot {lot.id} ({lot.lot_type}): Contributed {c.amount} Credits")
            
        # Verify final states
        session.refresh(grant_lot)
        session.refresh(topup_lot)
        print(f"\n--- Final Lot Status ---")
        print(f"Grant Lot Status: {grant_lot.status}, Remaining: {grant_lot.credits_remaining}")
        print(f"TopUp Lot Status: {topup_lot.status}, Remaining: {topup_lot.credits_remaining}")
        
        # 6. Rollover Demo
        print("\n--- Simulating Period Rollover ---")
        
        # A. Idempotency Check (Run Grant Job Again)
        print("Running Grant Job Again (Should do nothing for this sub)...")
        before_count = len(session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).all())
        run_grant_job(session)
        after_count = len(session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).all())
        print(f"Periods for sub: Before={before_count}, After={after_count} (Should be same)")
        
        # B. Expire Period 1
        print("Simulating Time Travel (End of Period 1)...")
        # Update Period 1 end date to past
        p1.period_end = datetime.utcnow() - timedelta(minutes=1)
        p1.status = "OPEN" # Ensure OPEN to test expiry logic
        # Update Grant Lot expiry to match (simulating time passing)
        # Actually logic checks lot.expires_at < now.
        grant_lot.expires_at = datetime.utcnow() - timedelta(minutes=1) 
        session.add(p1)
        session.add(grant_lot)
        session.commit()
        
        print("Running Expiry Job...")
        run_expiry_job(session)
        session.refresh(p1)
        session.refresh(grant_lot)
        print(f"Period 1 Status: {p1.status} (Expected CLOSED)")
        print(f"Grant Lot Status: {grant_lot.status} (Expected EXPIRED)")
        
        # C. New Period (Rollover)
        print("Simulating Start of Period 2...")
        # Advance Subscription dates
        sub.current_period_start = datetime.utcnow()
        sub.current_period_end = datetime.utcnow() + timedelta(days=30)
        session.add(sub)
        session.commit()
        
        print("Running Grant Job (Period 2)...")
        run_grant_job(session)
        
        periods = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id).order_by(SubscriptionPeriod.period_start)).all()
        print(f"Total Subscription Periods: {len(periods)}")
        if len(periods) == 2:
            p2 = periods[1]
            print(f"Period 2: ID {p2.id}, Start: {p2.period_start}, Granted: {p2.granted_credits}")
            l2 = session.get(CreditLot, p2.grant_lot_id)
            print(f"Grant Lot 2: ID {l2.id}, Balance: {l2.credits_remaining}")
        else:
            print("ERROR: Period 2 not created.")

if __name__ == "__main__":
    run_demo()
