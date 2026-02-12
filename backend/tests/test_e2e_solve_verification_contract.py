from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import matplotlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api import api_router
from app.auth import get_password_hash
from app.database import get_session
from app.models import User


def _load_cases():
    p = Path(__file__).parent / "golden_cases" / "solve_cases.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _fake_solver_result(question: str, llm_answer: str):
    return {
        "schema_version": "v1.0",
        "problem": {"original_text": question, "normalized_text": question, "detected_tasks": ["solve_equation"]},
        "classification": {"grade_band": "unknown", "domain": "algebra", "topic": "equation", "difficulty": "unknown"},
        "refusal": {"is_refusal": False, "reason": None, "safe_alternative": None},
        "assumptions": [],
        "steps": [],
        "final_answer": {"answer_text": llm_answer, "answer_latex": llm_answer, "values": []},
        "visuals": {"should_visualize": False, "decision_reason": "mock", "plots": []},
        "quality": {"confidence": 0.8, "common_mistakes": []},
        "telemetry": {"provider": "openai", "model": "gpt-mock", "latency_ms_total": 15, "validated": True},
    }


def test_e2e_solve_verification_contract(monkeypatch, session):
    monkeypatch.setenv("SOLVE_RULE_ENGINE_ENABLED", "false")
    user = session.get(User, 1)
    if user is None:
        user = User(
            id=1,
            email="e2e_contract@uask.ai",
            full_name="E2E Contract",
            password_hash=get_password_hash("admin1234"),
            role="admin",
            subscription_tier="standard",
            is_verified=True,
        )
        session.add(user)
        session.commit()

    class _FakeSolver:
        async def solve(self, *, problem_text, **kwargs):
            # Use test case map for deterministic LLM output.
            llm_answer = kwargs.get("_llm_answer_override")
            if llm_answer is None:
                llm_answer = "x=0"
            return _fake_solver_result(problem_text, llm_answer)

    fake_solver = _FakeSolver()

    # Patch resolve_profile and solver/billing deps.
    monkeypatch.setattr(
        "app.llm_profiles.profile_resolver.ProfileResolver.resolve_profile",
        lambda *args, **kwargs: SimpleNamespace(
            tier="standard",
            mode="minimal",
            max_output_tokens=1000,
            system_asset_path=None,
            system_relative_path=None,
            schema_asset_path=None,
            schema_relative_path=None,
            prompt_binding_meta={"features": {"allow_plot": False}},
        ),
    )
    monkeypatch.setattr("app.services.solver_v3.get_solver_v3", lambda: fake_solver)
    monkeypatch.setattr("app.services.subscription_service.subscription_service.get_or_create_subscription", lambda *args, **kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr("app.services.billing_service.billing_service.initiate_hold", lambda *args, **kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr("app.services.billing_service.billing_service.finalize_transaction", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.plot_integration.maybe_generate_plot", AsyncMock(return_value={"plot_generated": False}))

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    for case in _load_cases():
        # inject llm answer for this request by temporarily patching solve
        async def _solve(**kwargs):
            return _fake_solver_result(kwargs["problem_text"], case["llm_answer"])

        monkeypatch.setattr(fake_solver, "solve", _solve)

        resp = client.post(
            "/api/v1/solve_v3?user_id=1",
            json={"text_query": case["question"], "requested_mode": "minimal", "graph_mode": "off"},
        )
        assert resp.status_code == 200, f"{case['name']} failed with {resp.status_code}: {resp.text}"
        data = resp.json()

        # Stable contract fields
        assert "request_id" in data and data["request_id"]
        assert "attempt_id" in data and data["attempt_id"]
        assert "verified" in data
        assert "verification_method" in data
        assert "assumptions" in data
        assert "dropped_candidates" in data
        assert "final_solutions" in data
        assert "timing_ms" in data and "total" in data["timing_ms"]

        assert data["verified"] is case["expected_verified"], case["name"]
        assert data.get("unverified_reason") == case["expected_unverified_reason"], case["name"]

        for exp in case.get("expected_solutions", []):
            assert exp in (data.get("final_solutions") or []), f"{case['name']} missing expected solution {exp}"
        for bad in case.get("forbidden_solutions", []):
            assert bad not in (data.get("final_solutions") or []), f"{case['name']} should drop {bad}"
        for assumption in case.get("expected_assumptions", []):
            assert any(assumption in a for a in (data.get("assumptions") or [])), f"{case['name']} missing assumption {assumption}"


def test_plot_backend_is_headless_agg():
    assert str(matplotlib.get_backend()).lower() == "agg"
