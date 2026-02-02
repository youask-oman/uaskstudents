import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import app
from app.models import User, Subscription, Plan, UsageLedger
from app.services.subscription_service import subscription_service
import uuid

client = TestClient(app)

# Helper to setup a test user with specific plan features
@pytest.fixture
def test_user_setup(session: Session):
    # Create Plan
    plan = Plan(
        name="Test Plan Phase 4",
        slug="test-phase4",
        price_monthly_cents=1000,
        price_yearly_cents=10000,
        credits_per_month=1000,
        seats=1,
        is_active=True,
        features={
            "allow_research": True,
            "allow_verify": True,
            "daily_credit_cap": 200,
            "ocr_monthly_cap": 5,
            "voice_monthly_cap": 5
        },
        multipliers={
            "version": 2,
            "credits": {
                "solve": {
                    "free": {"text": 10, "snap_image": 20, "snap_pdf": 30, "voice": 40},
                    "standard": {"text": 15, "snap_image": 25, "snap_pdf": 35, "voice": 45},
                    "research": {"text": 50, "snap_image": 60, "snap_pdf": 70, "voice": 80},
                }
            }
        }
    )
    session.add(plan)
    session.commit()
    
    # Create User & Subscription
    user = User(email="tester@phase4.com", full_name="Phase4 Tester", hashed_password="pw")
    session.add(user)
    session.commit()
    
    sub = Subscription(
        user_id=user.id, 
        plan_id=plan.id, 
        credits_balance=500.0,
        feature_usage={"ocr": 0, "voice": 0}
    )
    session.add(sub)
    session.commit()
    
    return user, sub, plan

def test_estimator(session: Session, test_user_setup):
    user, sub, plan = test_user_setup
    
    # Text Standard
    res = client.post("/api/v1/credits/estimate", json={
        "tier": "standard",
        "requested_mode": "text",
        "features_used": {}
    }, headers={"X-User-ID": str(user.id)}) # Mock Auth Middleware if exists, or assume test environment bypass?
    # Our simple auth depends on dependency overrides in tests usually.
    # For now, let's assume we can call subscription service directly if API not easily mocked here without extensive setup.
    
    # Direct Service Test is often more reliable for logic verification
    action = {
        "tier": "standard",
        "mode": "text",
        "has_ocr": False,
        "has_voice": False,
        "reference_id": str(uuid.uuid4())
    }
    ent = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent["allowed"] is True
    assert ent["cost"] == 15 # From setup
    
    # Research setup
    action["tier"] = "research"
    ent = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent["allowed"] is True
    assert ent["cost"] == 50

def test_caps_enforcement(session: Session, test_user_setup):
    user, sub, plan = test_user_setup
    
    # 1. OCR Cap
    # Set usage to cap
    sub.feature_usage = {"ocr": 5}
    session.add(sub)
    session.commit()
    
    action = {
        "tier": "standard",
        "mode": "snap_image", # Imples OCR usage usually? Or explicit flag?
        "has_ocr": True,
        "reference_id": str(uuid.uuid4())
    }
    
    ent = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent["allowed"] is False
    assert ent["error_code"] == "CAP_EXCEEDED"
    
    # 2. Daily Cap
    # Insert ledger entries to fill daily cap (200)
    # Using 190 used, asking for 15 -> 205 > 200 -> Fail
    ledger = UsageLedger(
        subscription_id=sub.id,
        amount=190,
        transaction_type="DEBIT",
        meta={},
        reference_id="fill_daily"
    )
    session.add(ledger)
    session.commit()
    
    action = {"tier": "standard", "mode": "text", "has_ocr": False, "reference_id": str(uuid.uuid4())} # Cost 15
    ent = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent["allowed"] is False
    assert ent["error_code"] == "CAP_EXCEEDED"
    assert "Daily" in ent["reason"]

def test_idempotency(session: Session, test_user_setup):
    user, sub, plan = test_user_setup
    ref_id = str(uuid.uuid4())
    
    action = {"tier": "standard", "mode": "text", "has_ocr": False, "reference_id": ref_id}
    
    # First call
    ent1 = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent1["allowed"] is True
    assert ent1.get("status") != "already_processed"
    
    # Execute debit
    subscription_service.execute_debit(session, sub, ent1["cost"], ent1["meta"], ref_id)
    
    # Second call (same ref_id)
    ent2 = subscription_service.check_entitlement_and_debit(session, user.id, action)
    assert ent2["allowed"] is True
    assert ent2["status"] == "already_processed"
    assert ent2["cost"] == ent1["cost"]

def test_refund(session: Session, test_user_setup):
    user, sub, plan = test_user_setup
    start_bal = sub.credits_balance
    ref_id = str(uuid.uuid4())
    cost = 15
    
    # Charge
    subscription_service.execute_debit(session, sub, cost, {}, ref_id)
    session.refresh(sub)
    assert sub.credits_balance == start_bal - cost
    
    # Refund
    subscription_service.refund_credits(session, sub.id, cost, "Test Refund", ref_id)
    session.refresh(sub)
    assert sub.credits_balance == start_bal
    
    # Check Ledger
    refund_entry = session.exec(select(UsageLedger).where(UsageLedger.reference_id == ref_id, UsageLedger.transaction_type == "REFUND")).first()
    assert refund_entry is not None
