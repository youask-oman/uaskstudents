
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.models import User, Subscription, Plan, CreditLot, SubscriptionPeriod, UsageLedger
from app.jobs.grant_subscription_credits_job import run_grant_job
from app.jobs.expire_subscription_grants_job import run_expiry_job
from app.services.credit_lot_allocator import credit_lot_allocator

# Helper to ensure unique emails
def random_suffix():
    import uuid
    return str(uuid.uuid4())[:8]

def setup_user_and_plan(session, prefix):
    # Create Plan
    plan_slug = f"test_p3_{prefix}_{random_suffix()}"
    plan = Plan(slug=plan_slug, name="Test Plan", credits_per_month=100, price_monthly_cents=1000, 
                price_yearly_cents=10000,
                features={"monthly_credits_included": 100, "overage_policy": "paygo", "spend_order": "allowance_first"})
    session.add(plan)
    session.commit() # Get ID
    
    # Create User
    email = f"{prefix}_{random_suffix()}@test.com"
    user = User(email=email, full_name="Sub Tester", password_hash="x")
    session.add(user)
    session.commit()
    
    # Create Subscription
    start = datetime.utcnow()
    end = start + timedelta(days=30)
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        current_period_start=start,
        current_period_end=end,
        credits_balance=0.0
    )
    session.add(sub)
    session.commit()
    return user, sub, plan

def test_grant_job_flow(session: Session):
    user, sub, plan = setup_user_and_plan(session, "grant")
    
    # 1. Run Grant Job (Should succeed)
    count = run_grant_job(session)
    assert count >= 1 # Could affect other tests/seeds, but this user should be processed
    
    # Verify Period
    period = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).first()
    assert period is not None
    assert period.status == "OPEN"
    assert period.granted_credits == 100
    
    # Verify Lot
    lot = session.get(CreditLot, period.grant_lot_id)
    assert lot is not None
    assert lot.credits_remaining == 100
    assert lot.lot_type == "SUBSCRIPTION_GRANT"
    
    # 2. Run Grant Job Again (Idempotence)
    # Should not create new period or lot for THIS subscription
    initial_period_id = period.id
    initial_lot_id = lot.id
    
    count2 = run_grant_job(session)
    # Count2 might refer to other subscriptions, so checking count isn't robust if other data exists.
    # Instead, check that for THIS sub, no new period exists.
    
    periods = session.exec(select(SubscriptionPeriod).where(SubscriptionPeriod.subscription_id == sub.id)).all()
    assert len(periods) == 1
    assert periods[0].id == initial_period_id
    
    lots = session.exec(select(CreditLot).where(CreditLot.user_id == user.id)).all()
    # Should be only 1 if no previous lots
    assert len(lots) == 1
    assert lots[0].id == initial_lot_id

def test_expiry_job_flow(session: Session):
    user, sub, plan = setup_user_and_plan(session, "expiry")
    
    # Create an expired period manually
    past_start = datetime.utcnow() - timedelta(days=40)
    past_end = datetime.utcnow() - timedelta(days=10)
    
    # Grant Lot (Active but linked to past period)
    lot = CreditLot(
        user_id=user.id, subscription_id=sub.id, credits_total=100.0, credits_remaining=50.0,
        lot_type="SUBSCRIPTION_GRANT", status="ACTIVE", source="GRANT", 
        purchased_at=past_start, expires_at=past_end
    )
    session.add(lot)
    session.flush()
    
    period = SubscriptionPeriod(
        subscription_id=sub.id, period_start=past_start, period_end=past_end,
        status="OPEN", granted_credits=100, grant_lot_id=lot.id
    )
    session.add(period)
    session.commit()
    
    # Run Expiry Job
    run_expiry_job(session)
    
    session.refresh(period)
    session.refresh(lot)
    
    assert period.status == "CLOSED"
    assert lot.status == "EXPIRED"
    assert lot.credits_remaining == 0.0

def test_spend_order_priority(session: Session):
    user, sub, plan = setup_user_and_plan(session, "spend")
    
    # Setup Conflict:
    # 1. Early Expiring TopUp (Expires +5 days)
    # 2. Late Expiring Grant (Expires +30 days)
    # Logic: Standard FIFO prefers Early Expiring.
    # Policy: "allowance_first" prefers Grant regardless.
    
    early_expiring_topup = CreditLot(
        user_id=user.id, credits_total=50.0, credits_remaining=50.0,
        lot_type="TOPUP", status="ACTIVE", source="MANUAL_EARLY",
        purchased_at=datetime.utcnow() - timedelta(days=10),
        expires_at=datetime.utcnow() + timedelta(days=5) 
    )
    session.add(early_expiring_topup)
    
    grant = CreditLot(
        user_id=user.id, credits_total=20.0, credits_remaining=20.0,
        lot_type="SUBSCRIPTION_GRANT", status="ACTIVE", source="GRANT",
        purchased_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    session.add(grant)
    session.commit()
    
    # Create dummy usage ledger
    ledger = UsageLedger(
        subscription_id=sub.id, transaction_type="DEBIT", amount=10.0, 
        balance_after=0, reference_id="test_prio"
    )
    session.add(ledger)
    session.flush()

    # Consume 10 credits
    consumptions = credit_lot_allocator.consume_credits(
        session, user.id, 10.0, ledger.id, sub.id
    )
    session.commit()
    
    assert len(consumptions) == 1
    c = consumptions[0]
    
    # ASSERTION: Should use GRANT (ID matches grant lot)
    assert c.credit_lot_id == grant.id, "Allocator failed to prioritize SUBSCRIPTION_GRANT over early expiring TopUp"
    
    # Verify Balance
    session.refresh(grant)
    assert grant.credits_remaining == 10.0

def test_overage_policy_block(session: Session):
    user, sub, plan = setup_user_and_plan(session, "block")
    
    # Update Plan to BLOCK
    plan.features = {"monthly_credits_included": 100, "overage_policy": "block", "spend_order": "allowance_first"}
    session.add(plan)
    
    # 1. Grant 20 credits
    grant = CreditLot(
        user_id=user.id, credits_total=20.0, credits_remaining=20.0,
        lot_type="SUBSCRIPTION_GRANT", status="ACTIVE", source="GRANT",
        purchased_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    session.add(grant)
    
    # 2. Add 100 TOPUP credits
    topup = CreditLot(
        user_id=user.id, credits_total=100.0, credits_remaining=100.0,
        lot_type="TOPUP", status="ACTIVE", source="PAYMENT",
        purchased_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=365)
    )
    session.add(topup)
    session.commit()
    
    # Dummy Usage Ledger
    ledger = UsageLedger(
        subscription_id=sub.id, transaction_type="DEBIT", amount=50.0, 
        balance_after=0, reference_id="test_block"
    )
    session.add(ledger)
    session.flush()

    # Attempt to consume 50 credits
    # Since policy is BLOCK, it should only find 20 credits from GRANT.
    consumptions = credit_lot_allocator.consume_credits(
        session, user.id, 50.0, ledger.id, sub.id
    )
    
    total_consumed = sum(c.amount for c in consumptions)
    assert total_consumed == 20.0, f"BLOCK policy failed: consumed {total_consumed} instead of 20"
    
    # Verify Topup remains untouched
    session.refresh(topup)
    assert topup.credits_remaining == 100.0
