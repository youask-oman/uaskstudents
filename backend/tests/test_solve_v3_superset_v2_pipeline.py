from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.auth import get_password_hash
from app.models import JsonSchemaEntry, PromptTemplateEntry, PromptModeEnum, PromptRoleEnum, SystemConfig, User
from app.services.solve.superset_v2_pipeline import run_solve_v3_superset_v2

pytestmark = pytest.mark.asyncio


def _upsert_system_config(session, key: str, value: str):
    row = session.get(SystemConfig, key)
    if row:
        row.value = value
    else:
        row = SystemConfig(key=key, value=value, description="test")
        session.add(row)


def _seed_superset_test_assets(session):
    user = session.get(User, 1)
    if user is None:
        session.add(
            User(
                id=1,
                email="superset_v2_test@uask.ai",
                full_name="Superset V2 Test",
                password_hash=get_password_hash("admin1234"),
                role="admin",
                subscription_tier="standard",
                is_verified=True,
            )
        )

    schema_ids = [
        "solve_superset_v2.schema.json",
        "solve_llm_min_v2.schema.json",
        "solve_clarification_patch_v1.schema.json",
        "solve_repair_patch_v1.schema.json",
    ]
    for schema_id in schema_ids:
        schema = session.exec(
            select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id == schema_id).order_by(JsonSchemaEntry.version.desc())
        ).first()
        if schema:
            continue
        session.add(
            JsonSchemaEntry(
                schema_id=schema_id,
                content={"name": schema_id.replace(".schema.json", ""), "schema": {"type": "object", "additionalProperties": True}},
                version=1,
                is_active=True,
                updated_by="tests",
            )
        )

    prompt_ids = [
        "global_system_prompt_v2_compact.txt",
        "solve_orchestrator_developer_v2_compact.txt",
        "solve_output_contract_v2_compact.txt",
        "solve_explain_narrator_v2_compact.txt",
        "solve_plot_spec_v2_compact.txt",
        "solve_repair_verification_patch_v1.txt",
        "solve_clarification_patch_v1.txt",
    ]
    mode_by_prompt = {
        "solve_plot_spec_v2_compact.txt": PromptModeEnum.PLOT_SPEC,
        "solve_repair_verification_patch_v1.txt": PromptModeEnum.VERIFY,
    }
    for prompt_id in prompt_ids:
        row = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .order_by(PromptTemplateEntry.version.desc())
        ).first()
        if row:
            continue
        session.add(
            PromptTemplateEntry(
                prompt_id=prompt_id,
                mode=mode_by_prompt.get(prompt_id, PromptModeEnum.SOLVE),
                role=PromptRoleEnum.SYSTEM if "global_system" in prompt_id else PromptRoleEnum.DEVELOPER,
                content=f"TEST PROMPT {prompt_id}",
                version=1,
                is_active=True,
                updated_by="tests",
            )
        )

    _upsert_system_config(session, "SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_ORCHESTRATOR_DEV_PROMPT_ID", "solve_orchestrator_developer_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_patch_v1.txt")
    _upsert_system_config(session, "SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_patch_v1.txt")
    _upsert_system_config(session, "SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json")
    _upsert_system_config(session, "SOLVE_LLM_MIN_SCHEMA_ID", "solve_llm_min_v2.schema.json")
    _upsert_system_config(session, "SOLVE_CLARIFY_SCHEMA_ID", "solve_clarification_patch_v1.schema.json")
    _upsert_system_config(session, "SOLVE_REPAIR_SCHEMA_ID", "solve_repair_patch_v1.schema.json")
    _upsert_system_config(
        session,
        "SOLVE_TIER_POLICY_JSON",
        json.dumps(
            {
                "STANDARD": {"min_steps": 6, "max_steps": 10, "max_tokens": 2000, "narrator": False},
                "RESEARCH": {"min_steps": 6, "max_steps": 12, "max_tokens": 4000, "narrator": False},
                "FINAL": {"min_steps": 0, "max_steps": 3, "max_tokens": 1200, "narrator": False},
                "FREE": {"min_steps": 0, "max_steps": 3, "max_tokens": 1200, "narrator": False},
            }
        ),
    )
    session.commit()


def _restore_default_system_configs(session):
    _upsert_system_config(session, "SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_ORCHESTRATOR_DEV_PROMPT_ID", "solve_orchestrator_developer_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2_compact.txt")
    _upsert_system_config(session, "SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_patch_v1.txt")
    _upsert_system_config(session, "SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_patch_v1.txt")
    _upsert_system_config(session, "SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json")
    _upsert_system_config(session, "SOLVE_LLM_MIN_SCHEMA_ID", "solve_llm_min_v2.schema.json")
    _upsert_system_config(session, "SOLVE_CLARIFY_SCHEMA_ID", "solve_clarification_patch_v1.schema.json")
    _upsert_system_config(session, "SOLVE_REPAIR_SCHEMA_ID", "solve_repair_patch_v1.schema.json")
    _upsert_system_config(session, "SOLVE_TIER_POLICY_JSON", json.dumps({}))
    session.commit()


async def test_superset_v2_multi_question_returns_clarification(monkeypatch, session):
    _seed_superset_test_assets(session)

    try:
        class _FakeSolver:
            async def _call_llm_with_schema(self, *args, **kwargs):
                return (
                    {
                        "schema_version": "clarification_patch_v1",
                        "action": "clarification",
                        "reason": "Multiple questions found.",
                        "questions": [{"id": "q1", "question": "Pick one", "choices": ["Q1", "Q2"]}],
                    },
                    {"input": 10, "output": 5, "total": 15},
                    {"finish_reason": "stop"},
                    "gpt-5-mini",
                    "{}",
                    3,
                )

            def _check_status_and_validate(self, *args, **kwargs):  # pragma: no cover
                return True, None, args[0], [], False

        monkeypatch.setattr("app.services.solve.superset_v2_pipeline.get_solver_v3", lambda: _FakeSolver())

        result = await run_solve_v3_superset_v2(
            session=session,
            user_id=1,
            problem_text="1) Solve x+1=2\n\n2) Solve x+2=5",
            requested_tier="standard",
            requested_mode="detailed",
            graph_mode="on",
            trusted_context={},
        )

        assert result["response_kind"] == "clarification"
        assert result["clarification"]["needs_clarification"] is True
        assert result["steps"] == []
        assert result["final_answer"] is None
        assert result["verification"]["verification_method"] == "none"
    finally:
        _restore_default_system_configs(session)


async def test_superset_v2_single_question_verified_and_plot(monkeypatch, session):
    _seed_superset_test_assets(session)

    payload = {
        "schema_version": "llm_min_v2",
        "response_kind": "solution",
        "language": {"preferred_response_language": "en", "response_language": "en", "user_language": "en"},
        "assumptions": ["x is real"],
        "steps": [
            {
                "index": 1,
                "title": "Factor",
                "explanation": "x^2-4=(x-2)(x+2)",
                "math_latex": ["x^2-4=(x-2)(x+2)"],
            }
        ],
        "final_answer": {"answer_text": "x=2,-2", "answer_latex": "x=2,-2", "values": []},
        "candidates": [{"value": "2", "latex": "2", "notes": None}, {"value": "-2", "latex": "-2", "notes": None}],
        "plot": {
            "should_visualize": True,
            "decision_reason": "plot requested",
            "recipe": {
                "plot_intent": "function_2d",
                "title": "Quadratic",
                "axis_labels": {"x": "x", "y": "y"},
                "domain": {"x_min": -3, "x_max": 3, "y_min": -5, "y_max": 5},
                "expressions": ["x^2-4"],
                "symbols": ["x"],
                "sampling": {"n_points": 30},
                "key_points": [{"label": "x=2", "x": 2, "y": 0}],
            },
        },
        "clarification": {"needs_clarification": False, "questions": [], "note": None},
        "refusal": {"is_refusal": False, "reason": None, "safe_alternative": None},
        "confidence": 0.9,
    }

    class _FakeSolver:
        async def _call_llm_with_schema(self, *args, **kwargs):
            return payload, {"input": 101, "output": 55, "total": 156}, {"finish_reason": "stop"}, "gpt-5-mini", json.dumps(payload), 5

        def _check_status_and_validate(self, data, status_info, schema, raw_text=None):
            return True, None, data, [], False

        async def _repair_response(self, *args, **kwargs):  # pragma: no cover
            return payload, json.dumps(payload)

    try:
        monkeypatch.setattr("app.services.solve.superset_v2_pipeline.get_solver_v3", lambda: _FakeSolver())
        monkeypatch.setattr("app.services.solve.superset_v2_pipeline.maybe_generate_plot", lambda **kwargs: SimpleNamespace())

        async def _fake_plot(*args, **kwargs):
            return {
                "plot_generated": True,
                "spec": {
                    "plotly_json": {"data": [{"name": "f", "x": [-2, 0, 2], "y": [0, -4, 0], "mode": "lines"}]},
                },
            }

        monkeypatch.setattr("app.services.solve.superset_v2_pipeline.maybe_generate_plot", _fake_plot)
        monkeypatch.setattr("app.services.solve.superset_v2_pipeline.format_plot_for_response", lambda result, plot_data: result)

        result = await run_solve_v3_superset_v2(
            session=session,
            user_id=1,
            problem_text="x^2-4=0",
            requested_tier="standard",
            requested_mode="detailed",
            graph_mode="on",
            trusted_context={},
        )

        assert result["verification"]["verified"] is True
        assert result["verification"]["verification_method"] == "symbolic"
        assert len(result["steps"]) >= 6
        assert result["visuals"]["should_visualize"] is True
        assert len(result["visuals"]["plots"]) >= 1
        assert "timing_ms" in result and "openai" in result["timing_ms"]
    finally:
        _restore_default_system_configs(session)
