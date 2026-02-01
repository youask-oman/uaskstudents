import pytest

from app.services.solver_v3 import SolverV3


class FakeManager:
    primary_provider = "openai"
    fallback_enabled = False

    def get_provider_chain(self):
        return ["openai"]

    def get_fallback_provider(self):
        return None

    def note_error(self, provider, error):
        return None


@pytest.mark.asyncio
async def test_repair_succeeds_after_invalid_json(monkeypatch):
    solver = SolverV3(llm_manager=FakeManager())

    async def fake_call(*args, **kwargs):
        return {"_raw": "not json"}, {"input": 0, "output": 0, "total": 0, "cached": None, "payload": {}}, {"status": "completed", "finish_reason": "stop"}, "mock-model", "not json"

    check_calls = {"count": 0}

    def fake_check(data, status, schema, raw_text=None):
        check_calls["count"] += 1
        if check_calls["count"] == 1:
            return False, "Schema Validation Failed", None, [{"type": "parse_error", "message": "bad json", "path": "$"}]
        return True, None, {"problem": {}, "classification": {}, "steps": [], "final_answer": {}}, []

    async def fake_repair(*args, **kwargs):
        return {"problem": {}, "classification": {}, "steps": [], "final_answer": {}}, "{\"ok\":true}"

    monkeypatch.setattr(solver, "_call_llm_with_schema", fake_call)
    monkeypatch.setattr(solver, "_check_status_and_validate", fake_check)
    monkeypatch.setattr(solver, "_repair_response", fake_repair)

    result = await solver.solve("2+2", requested_mode="detailed")
    assert result.get("telemetry", {}).get("repaired") is True
    assert result.get("telemetry", {}).get("repair_attempts") == 1


@pytest.mark.asyncio
async def test_repair_fails_returns_hard_schema_error(monkeypatch):
    solver = SolverV3(llm_manager=FakeManager())

    async def fake_call(*args, **kwargs):
        return {"_raw": "not json"}, {"input": 0, "output": 0, "total": 0, "cached": None, "payload": {}}, {"status": "completed", "finish_reason": "stop"}, "mock-model", "not json"

    def fake_check(data, status, schema, raw_text=None):
        return False, "Schema Validation Failed", None, [{"type": "schema_error", "message": "missing field", "path": "$.problem"}]

    repair_calls = {"count": 0}

    async def fake_repair(*args, **kwargs):
        repair_calls["count"] += 1
        return {"_raw": "still invalid"}, "still invalid"

    monkeypatch.setattr(solver, "_call_llm_with_schema", fake_call)
    monkeypatch.setattr(solver, "_check_status_and_validate", fake_check)
    monkeypatch.setattr(solver, "_repair_response", fake_repair)

    result = await solver.solve("2+2", requested_mode="detailed")
    assert result.get("error_type") == "LLM_SCHEMA_INVALID"
    assert repair_calls["count"] == 1
    assert result.get("telemetry", {}).get("repair_attempts") == 1


@pytest.mark.asyncio
async def test_schema_mismatch_repair_succeeds(monkeypatch):
    solver = SolverV3(llm_manager=FakeManager())

    async def fake_call(*args, **kwargs):
        return {"bad": "shape"}, {"input": 0, "output": 0, "total": 0, "cached": None, "payload": {}}, {"status": "completed", "finish_reason": "stop"}, "mock-model", "{\"bad\":\"shape\"}"

    check_calls = {"count": 0}

    def fake_check(data, status, schema, raw_text=None):
        check_calls["count"] += 1
        if check_calls["count"] == 1:
            return False, "Schema Validation Failed", None, [{"type": "schema_error", "message": "wrong keys", "path": "$"}]
        return True, None, {"problem": {}, "classification": {}, "steps": [], "final_answer": {}}, []

    async def fake_repair(*args, **kwargs):
        return {"problem": {}, "classification": {}, "steps": [], "final_answer": {}}, "{\"fixed\":true}"

    monkeypatch.setattr(solver, "_call_llm_with_schema", fake_call)
    monkeypatch.setattr(solver, "_check_status_and_validate", fake_check)
    monkeypatch.setattr(solver, "_repair_response", fake_repair)

    result = await solver.solve("2+2", requested_mode="detailed")
    assert result.get("telemetry", {}).get("repaired") is True


@pytest.mark.asyncio
async def test_only_one_repair_attempt(monkeypatch):
    solver = SolverV3(llm_manager=FakeManager())

    async def fake_call(*args, **kwargs):
        return {"_raw": "bad"}, {"input": 0, "output": 0, "total": 0, "cached": None, "payload": {}}, {"status": "completed", "finish_reason": "stop"}, "mock-model", "bad"

    def fake_check(data, status, schema, raw_text=None):
        return False, "Schema Validation Failed", None, [{"type": "schema_error", "message": "invalid", "path": "$"}]

    repair_calls = {"count": 0}

    async def fake_repair(*args, **kwargs):
        repair_calls["count"] += 1
        return {"_raw": "still bad"}, "still bad"

    monkeypatch.setattr(solver, "_call_llm_with_schema", fake_call)
    monkeypatch.setattr(solver, "_check_status_and_validate", fake_check)
    monkeypatch.setattr(solver, "_repair_response", fake_repair)

    await solver.solve("2+2", requested_mode="detailed")
    assert repair_calls["count"] == 1
