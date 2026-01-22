import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api import api_router
from app.database import get_session
from app.models import RequestEvent, UsageLedger, User, Subscription, Plan
from app.services.admin.analytics_service import _percentile, _error_category, _classify_question_mode


fastapi_app = FastAPI()
fastapi_app.include_router(api_router)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session
    fastapi_app.dependency_overrides[get_session] = get_session_override
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()


def test_percentile_helpers():
    values = [10, 20, 30, 40]
    assert _percentile(values, 50) == 25.0
    assert _percentile(values, 0) == 10.0
    assert _percentile(values, 100) == 40.0
    assert _error_category("schema_validation_error") == "schema"
    assert _error_category("stream_disconnect") == "streaming"


def test_classify_question_mode():
    event = RequestEvent(learning_mode="study", mode="minimal")
    assert _classify_question_mode(event) == "study"
    event = RequestEvent(learning_mode="solve", mode="minimal")
    assert _classify_question_mode(event) == "quick"
    event = RequestEvent(learning_mode="solve", mode="detailed")
    assert _classify_question_mode(event) == "solve"


def test_admin_analytics_overview_endpoint(client, session):
    now = datetime.utcnow()
    user = User(email="admin@test.com", full_name="Admin", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)

    plan = Plan(name="Free", slug="free", credits_per_month=10, price_monthly_cents=0, price_yearly_cents=0)
    session.add(plan)
    session.commit()
    subscription = Subscription(user_id=user.id, plan_id=plan.id, current_period_end=now + timedelta(days=30))
    session.add(subscription)
    session.commit()

    event_ok = RequestEvent(
        request_id="req-ok",
        user_id=user.id,
        created_at=now,
        mode="minimal",
        learning_mode="solve",
        tokens_in=120,
        tokens_out=240,
        tokens_total=360,
        cost_usd=0.00018,
        latency_ms=1200,
        status="ok",
        schema_valid=True,
        verification_pass=True,
        is_stream=False,
        is_cached=False,
        credit_deducted=True
    )
    event_err = RequestEvent(
        request_id="req-err",
        user_id=user.id,
        created_at=now,
        mode="minimal",
        learning_mode="solve",
        tokens_in=50,
        tokens_out=0,
        tokens_total=50,
        latency_ms=800,
        status="error",
        error_type="schema_validation"
    )
    session.add(event_ok)
    session.add(event_err)

    ledger = UsageLedger(
        subscription_id=subscription.id,
        transaction_type="DEBIT",
        amount=1.0,
        balance_after=9.0,
        reference_id="req-ok"
    )
    session.add(ledger)
    session.commit()

    response = client.get("/admin/analytics/overview?range=7d")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["questions_today"]["value"] >= 2
    assert payload["kpis"]["credit_deductions_today"]["value"] == 1
