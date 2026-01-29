
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from datetime import datetime
from app.models import User, CreditLot, BillingLedger, SystemConfig
from app.services.credit_wallet_service import credit_wallet_service
from app.services.billing_service import billing_service
from app.services.pricing_service import pricing_service, DEFAULT_PRICING_CONFIG

# Setup In-Memory DB for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed initial config
        import json
        config = DEFAULT_PRICING_CONFIG.copy()
        config["token_billing"]["usd_per_1000_tokens"] = 0.05 # $0.05 per 1k tokens
        config["token_billing"]["uask_fee_tokens_per_question"] = 700
        
        session.add(SystemConfig(key="pricing", value=json.dumps(config)))
        session.commit()
        
        yield session

@pytest.fixture(name="user")
def user_fixture(session):
    user = User(
        email="test@example.com", 
        full_name="Test User",
        password_hash="hash"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_estimate_calculation(session):
    # Action: solve_tutor
    # Input: 300, Output: 2000
    # Fee: 700
    # Total Billable: 300 + 2000 + 700 = 3000
    # Units (1000): ceil(3000/1000) = 3
    # USD: 3 * 0.05 = $0.15
    # Credits: ceil(0.15 * 25) = ceil(3.75) = 4.0
    
    cred, usd, tokens, fee, _ = pricing_service.calculate_estimate_token_cost(
        "solve_tutor", 300, 2000, session
    )
    
    assert fee == 700
    assert tokens == 3000
    assert cred == 4.0
    assert usd == 0.15

def test_workflow_success_overestimate(session, user):
    # Init Balance: 100
    credit_wallet_service.add_credits(session, user.id, 100.0, "init")
    
    # 1. Pending (Estimate High)
    # Est: Input 500, Output 3800 => 4300 raw + 700 fee = 5000 total
    # Units: 5. USD: 5 * 0.05 = 0.25. Credits: 0.25 * 25 = 6.25 -> 7.0
    
    ledger = billing_service.create_pending_transaction(
        session, user.id, "solve_tutor", 
        estimated_input_tokens=500, 
        estimated_output_tokens=3800
    )
    
    assert ledger.status == "PENDING"
    assert ledger.estimated_credits == 7.0
    assert credit_wallet_service.get_balance(session, user.id) == 93.0 # 100 - 7
    
    # 2. Settle (Actual Low)
    # Act: Input 500, Output 800 => 1300 raw + 700 fee = 2000 total
    # Units: 2. USD: 2 * 0.05 = 0.10. Credits: 0.10 * 25 = 2.5 -> 3.0
    
    billing_service.settle_transaction(
        session, ledger.id, 
        actual_input_tokens=500, 
        actual_output_tokens=800
    )
    
    session.refresh(ledger)
    assert ledger.status == "SETTLED"
    assert ledger.actual_credits == 3.0
    assert ledger.delta_credits == -4.0 # 3.0 - 7.0 = -4.0 (Refund)
    
    # Balance should be 93 + 4 = 97
    assert credit_wallet_service.get_balance(session, user.id) == 97.0

def test_workflow_success_underestimate(session, user):
    # Init Balance: 10
    credit_wallet_service.add_credits(session, user.id, 10.0, "init")
    
    # 1. Pending (Estimate Low)
    # Est: 300 in, 700 out + 700 = 1700 => 2 units => $0.10 => 3 credits (ceil(2.5))
    ledger = billing_service.create_pending_transaction(
        session, user.id, "solve_quick", 300, 700
    )
    
    assert ledger.estimated_credits == 3.0
    assert credit_wallet_service.get_balance(session, user.id) == 7.0
    
    # 2. Settle (Actual High)
    # Act: 300 in, 3000 out => 3300 + 700 = 4000 => 4 units => $0.20 => 5 credits
    billing_service.settle_transaction(
        session, ledger.id, 300, 3000
    )
    
    session.refresh(ledger)
    assert ledger.actual_credits == 5.0
    assert ledger.delta_credits == 2.0 # 5 - 3 = 2 (Charge)
    
    # Balance: 7 - 2 = 5
    assert credit_wallet_service.get_balance(session, user.id) == 5.0

def test_workflow_fail_refund(session, user):
    credit_wallet_service.add_credits(session, user.id, 10.0, "init")
    
    # Pending: Charge 3 credits
    ledger = billing_service.create_pending_transaction(
         session, user.id, "solve_quick", 300, 700
    )
    assert credit_wallet_service.get_balance(session, user.id) == 7.0
    
    # Fail
    billing_service.fail_transaction(session, ledger.id, "Timeout")
    
    session.refresh(ledger)
    assert ledger.status == "FAILED_REFUNDED"
    assert ledger.credits_charged == 0.0
    
    # Full Refund: 7 + 3 = 10
    assert credit_wallet_service.get_balance(session, user.id) == 10.0
