from app.api import _validate_stream_payload


def test_stream_business_rule_enforces_min_steps_for_ok_status():
    payload = {
        "solution": {"status": "ok", "steps": []},
        "plot": {"plot_specs": None},
        "verification": {"requested": False, "status": "not_requested", "checks": []},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert any("requires at least 4 steps" in err for err in errors)


def test_stream_business_rules_enforce_plot_and_verification_constraints():
    payload = {
        "solution": {"status": "needs_clarification", "steps": [{"step_id": 1}]},
        "plot": {"plot_specs": {"x": [1, 2]}},
        "verification": {"requested": False, "status": "verified", "checks": [{"check_id": "c1"}]},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert any("needs_clarification" in err for err in errors)
    assert any("plot.plot_specs must be null" in err for err in errors)
    assert any("verification.status must be 'not_requested'" in err for err in errors)
    assert any("verification.checks must be empty" in err for err in errors)


def test_stream_validation_returns_empty_for_valid_payload():
    payload = {
        "solution": {"status": "ok", "steps": [{}, {}, {}, {}]},
        "plot": {"plot_specs": None},
        "verification": {"requested": False, "status": "not_requested", "checks": []},
    }
    errors = _validate_stream_payload(payload, {"type": "object"})
    assert errors == []
