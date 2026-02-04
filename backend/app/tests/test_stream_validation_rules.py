import json
from pathlib import Path

from app.api import _build_schema_valid_stream_error_payload, _validate_stream_payload


def test_stream_business_rule_enforces_min_steps_for_ok_status():
    payload = {
        "solution": {"status": "ok", "steps": []},
        "plot": {"plot_needed": True, "plot_specs": [{"plot_id": "p1"}]},
        "verification": {"requested": True, "status": "verified", "checks": [{"check_id": "c1"}, {"check_id": "c2"}, {"check_id": "c3"}]},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert any("requires at least 4 steps" in err for err in errors)


def test_stream_business_rules_enforce_plot_and_verification_requirements():
    payload = {
        "solution": {"status": "needs_clarification", "steps": [{"step_id": 1}]},
        "plot": {"plot_needed": True, "plot_specs": []},
        "verification": {"requested": True, "status": "verified", "checks": [{"check_id": "c1"}]},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert any("needs_clarification" in err for err in errors)
    assert any("plot.plot_needed=true requires at least one plot spec" in err for err in errors)
    assert any("verification.requested=true requires at least 3 checks" in err for err in errors)


def test_stream_validation_returns_empty_for_valid_payload():
    payload = {
        "solution": {"status": "ok", "steps": [{}, {}, {}, {}]},
        "plot": {"plot_needed": True, "plot_specs": [{"plot_id": "p1"}]},
        "verification": {"requested": True, "status": "verified", "checks": [{"check_id": "c1"}, {"check_id": "c2"}, {"check_id": "c3"}]},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert errors == []


def test_stream_error_payload_is_schema_valid_and_limits_debug_errors():
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "backend"
        / "app"
        / "schemas"
        / "youask_math_solver_standard_solve_extreme_v1.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    error_payload = _build_schema_valid_stream_error_payload(
        problem_text="x^2=9",
        provider="openai",
        model="mightykatun/gpt-5-mini",
        tier="STANDARD",
        mode="SOLVE",
        prompt_id="solve_standard_extreme_detailed_v1",
        validation_errors=[f"err-{i}" for i in range(15)],
        schema_config=schema,
    )
    errors = _validate_stream_payload(error_payload, schema)
    assert errors == []
    assert error_payload["solution"]["status"] == "error"
    assert len(error_payload["meta"]["debug"]["validation_errors"]) == 10
