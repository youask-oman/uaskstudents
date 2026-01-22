import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api import api_router
from app.database import get_session
from app.models import Plan, PlanPromptLink, PromptAsset, Subscription, UsageLedger, User


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


def seed_plan_assets_and_user(session: Session):
    plan = Plan(
        name="Student Standard",
        slug="student_standard",
        credits_per_month=100,
        price_monthly_cents=0,
        price_yearly_cents=0,
        seats=1,
        features={
            "ocr_monthly_cap": 10,
            "voice_monthly_cap": 10
        },
        multipliers={
            "text_concise": 1,
            "text_detailed": 2,
            "ocr_add": 1,
            "voice_add": 1
        },
        is_active=True
    )
    session.add(plan)

    system_asset = PromptAsset(key="test:system", kind="system", path="llm_profiles/shared/minimal_system.txt")
    schema_asset = PromptAsset(key="test:schema", kind="schema", path="llm_profiles/shared/minimal_schema.json")
    session.add(system_asset)
    session.add(schema_asset)
    session.commit()

    link = PlanPromptLink(
        plan_id=plan.id,
        mode="minimal",
        system_prompt_asset_id=system_asset.id,
        schema_prompt_asset_id=schema_asset.id
    )
    session.add(link)

    user = User(
        email="student@example.com",
        full_name="Test Student",
        password_hash="test",
        subscription_tier="pro",
        subscription_status="active"
    )
    session.add(user)
    session.commit()

    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        current_period_end=datetime.utcnow() + timedelta(days=30),
        credits_balance=10.0,
        credits_used_this_period=0.0,
        feature_usage={}
    )
    session.add(subscription)
    session.commit()
    session.refresh(user)
    return user, subscription


def minimal_solver_result():
    return {
        "problem": {"goal": "Solve", "input": "x+1=2"},
        "final_answer": {"answer_text": "x=1", "answer_latex": "x=1", "units": None},
        "steps": [],
        "verification": {"method": "N/A", "work_latex": "", "conclusion": ""},
        "visuals": {"should_visualize": False, "plots": []},
        "quality": {"confidence": 0.5, "common_mistakes": [], "next_practice": []},
        "assumptions": [],
        "refusal": {"is_refusal": False, "reason": "", "safe_alternative": ""},
        "telemetry": {
            "total_tokens": 10,
            "input_tokens": 5,
            "output_tokens": 5,
            "cached_tokens": 0,
            "openai_payload": {"response_format_schema_name": "solve_response_v3"},
            "openai_calls_count": 1
        }
    }


def test_quick_text_solve_debits_credits(client, session):
    user, subscription = seed_plan_assets_and_user(session)

    with patch("app.llm_profiles.asset_loader.AssetLoader.get_asset_content") as mock_loader:
        mock_loader.side_effect = lambda asset: {} if asset.kind == "schema" else "SYSTEM"
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
            solver = AsyncMock()
            solver.solve = AsyncMock(return_value=minimal_solver_result())
            mock_get_solver.return_value = solver

            response = client.post(
                f"/solve_v3?user_id={user.id}",
                json={
                    "text_query": "Solve x+1=2",
                    "requested_mode": "minimal",
                    "trusted_context": {"learning_mode": "solve"}
                }
            )

    assert response.status_code == 200
    session.refresh(subscription)
    assert subscription.credits_balance == 9.0
    ledger_entries = session.exec(select(UsageLedger).where(UsageLedger.subscription_id == subscription.id)).all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].transaction_type == "DEBIT"


def test_ocr_solve_debits_credits_and_ocr(client, session):
    user, subscription = seed_plan_assets_and_user(session)

    with patch("app.llm_profiles.asset_loader.AssetLoader.get_asset_content") as mock_loader:
        mock_loader.side_effect = lambda asset: {} if asset.kind == "schema" else "SYSTEM"
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
            solver = AsyncMock()
            solver.solve = AsyncMock(return_value=minimal_solver_result())
            mock_get_solver.return_value = solver

            response = client.post(
                f"/solve_v3?user_id={user.id}",
                json={
                    "text_query": "Solve x+1=2",
                    "image_url": "http://example.com/problem.png",
                    "requested_mode": "minimal",
                    "trusted_context": {"learning_mode": "solve"}
                }
            )

    assert response.status_code == 200
    session.refresh(subscription)
    assert subscription.credits_balance == 8.0
    assert subscription.feature_usage.get("ocr") == 1


def test_cache_hit_does_not_debit(client, session):
    user, subscription = seed_plan_assets_and_user(session)
    cached_result = minimal_solver_result()

    with patch("app.llm_profiles.asset_loader.AssetLoader.get_asset_content") as mock_loader:
        mock_loader.side_effect = lambda asset: {} if asset.kind == "schema" else "SYSTEM"
        with patch("app.services.solve.cache_service.cache_service.get_cached_solution") as mock_cache:
            mock_cache.return_value = cached_result

            response = client.post(
                f"/solve_v3?user_id={user.id}",
                json={
                    "text_query": "Solve x+1=2",
                    "requested_mode": "minimal",
                    "trusted_context": {"learning_mode": "solve"}
                }
            )

    assert response.status_code == 200
    session.refresh(subscription)
    assert subscription.credits_balance == 10.0
    ledger_entries = session.exec(select(UsageLedger).where(UsageLedger.subscription_id == subscription.id)).all()
    assert len(ledger_entries) == 0
