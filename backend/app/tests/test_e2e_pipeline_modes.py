import json
import uuid

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import PromptTierEnum, PromptModeEnum, PromptRoleEnum
from app.services.prompt_registry_service import prompt_registry_service
from app.services.mode_execution_service import mode_execution_service, ModeExecutionError


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeClient:
    async def generate(self, **kwargs):
        messages = kwargs.get("messages") or []
        combined = " ".join(str(msg.get("content", "")) for msg in messages if isinstance(msg, dict))
        if "DEV_FREE_SOLVE" in combined:
            payload = {"answer_text": "3", "steps": []}
        elif "DEV_STANDARD_SOLVE" in combined:
            payload = {"answer_text": "x=7", "steps": [{"id": 1}]}
        elif "DEV_RESEARCH_SOLVE" in combined:
            payload = {"answer_text": "complex", "steps": [{"id": 1}, {"id": 2}]}
        elif "DEV_VERIFY" in combined:
            payload = {"is_valid": True, "checks": ["ok"]}
        elif "DEV_PLOT_TRIGGER" in combined:
            payload = {"should_plot": True, "reason": "graphable"}
        elif "DEV_PLOT_SPEC" in combined:
            payload = {"attach_to_step_id": 1, "data": [], "layout": {}}
        else:
            payload = {"unknown": True}
        return FakeResponse(json.dumps(payload))


class FakeManager:
    def __init__(self):
        self.primary_provider = "ollama"
        self.fallback_enabled = False
        self.last_error = {}

    def get_provider_chain(self):
        return ["ollama"]

    def get_client(self, provider):
        return FakeClient()

    def note_error(self, provider, error):
        self.last_error[provider] = str(error)


class GarbageClient:
    async def generate(self, **kwargs):
        return FakeResponse("هذا نص غير صالح")


class GarbageManager(FakeManager):
    def get_client(self, provider):
        return GarbageClient()


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "e2e_modes.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def seed_registry(session: Session):
    prompt_registry_service.update_prompt(session, "global_system_prompt_v1", "GLOBAL", None, PromptModeEnum.SOLVE, PromptRoleEnum.SYSTEM, "test")
    prompt_registry_service.update_prompt(session, "solve_free_minimal_v1", "DEV_FREE_SOLVE", PromptTierEnum.FREE, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "test")
    prompt_registry_service.update_prompt(session, "solve_standard_extreme_detailed_v1", "DEV_STANDARD_SOLVE", PromptTierEnum.STANDARD, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "test")
    prompt_registry_service.update_prompt(session, "solve_research_v1", "DEV_RESEARCH_SOLVE", PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "test")
    prompt_registry_service.update_prompt(session, "verify_v1", "DEV_VERIFY", None, PromptModeEnum.VERIFY, PromptRoleEnum.DEVELOPER, "test")
    prompt_registry_service.update_prompt(session, "plot_trigger_v1", "DEV_PLOT_TRIGGER", None, PromptModeEnum.PLOT_TRIGGER, PromptRoleEnum.DEVELOPER, "test")
    prompt_registry_service.update_prompt(session, "plot_spec_v1", "DEV_PLOT_SPEC", None, PromptModeEnum.PLOT_SPEC, PromptRoleEnum.DEVELOPER, "test")

    prompt_registry_service.update_schema(session, "youask_math_solver_response_v1", {"type": "object", "required": ["answer_text", "steps"], "properties": {"answer_text": {"type": "string"}, "steps": {"type": "array"}}}, "test")
    prompt_registry_service.update_schema(session, "youask_math_solver_standard_solve_extreme_v1", {"type": "object", "required": ["answer_text", "steps"], "properties": {"answer_text": {"type": "string"}, "steps": {"type": "array"}}}, "test")
    prompt_registry_service.update_schema(session, "youask_math_solver_research_solve_v1", {"type": "object", "required": ["answer_text", "steps"], "properties": {"answer_text": {"type": "string"}, "steps": {"type": "array"}}}, "test")
    prompt_registry_service.update_schema(session, "youask_math_solver_verify_v1", {"type": "object", "required": ["is_valid", "checks"], "properties": {"is_valid": {"type": "boolean"}, "checks": {"type": "array"}}}, "test")
    prompt_registry_service.update_schema(session, "youask_plot_trigger_v1", {"type": "object", "required": ["should_plot", "reason"], "properties": {"should_plot": {"type": "boolean"}, "reason": {"type": "string"}}}, "test")
    prompt_registry_service.update_schema(session, "youask_plot_spec_v1", {"type": "object", "required": ["attach_to_step_id", "data", "layout"], "properties": {"attach_to_step_id": {"type": "integer"}, "data": {"type": "array"}, "layout": {"type": "object"}}}, "test")

    prompt_registry_service.activate_binding(session, PromptTierEnum.FREE, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_free_minimal_v1", "youask_math_solver_response_v1", "test")
    prompt_registry_service.activate_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_standard_extreme_detailed_v1", "youask_math_solver_standard_solve_extreme_v1", "test")
    prompt_registry_service.activate_binding(session, PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_research_v1", "youask_math_solver_research_solve_v1", "test")
    prompt_registry_service.activate_binding(session, PromptTierEnum.FREE, PromptModeEnum.VERIFY, "global_system_prompt_v1", "verify_v1", "youask_math_solver_verify_v1", "test")
    prompt_registry_service.activate_binding(session, PromptTierEnum.FREE, PromptModeEnum.PLOT_TRIGGER, "global_system_prompt_v1", "plot_trigger_v1", "youask_plot_trigger_v1", "test")
    prompt_registry_service.activate_binding(session, PromptTierEnum.FREE, PromptModeEnum.PLOT_SPEC, "global_system_prompt_v1", "plot_spec_v1", "youask_plot_spec_v1", "test")


@pytest.mark.asyncio
async def test_e2e_modes(session, monkeypatch):
    seed_registry(session)
    monkeypatch.setattr(mode_execution_service, "_llm_manager", FakeManager())

    free = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.SOLVE,
        question_payload={"image_text": "2+1"},
        context_payload={"input_type": "image"},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert free["ok"] is True
    assert free["output"]["answer_text"] == "3"

    standard = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        question_payload={"problem": "x+2=9"},
        context_payload={},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert standard["ok"] is True

    research = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.RESEARCH,
        mode=PromptModeEnum.SOLVE,
        question_payload={"problem": "complex"},
        context_payload={},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert research["ok"] is True

    verify = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.VERIFY,
        question_payload={"candidate": "x=3"},
        context_payload={},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert verify["ok"] is True
    assert verify["output"]["is_valid"] is True

    plot_trigger = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.PLOT_TRIGGER,
        question_payload={"problem": "y=x^2"},
        context_payload={},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert plot_trigger["ok"] is True
    assert "should_plot" in plot_trigger["output"]

    plot_spec = await mode_execution_service.run(
        session=session,
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.PLOT_SPEC,
        question_payload={"problem": "y=x^2"},
        context_payload={},
        runtime_hints={},
        request_id=str(uuid.uuid4()),
    )
    assert plot_spec["ok"] is True
    assert plot_spec["output"]["attach_to_step_id"] == 1


@pytest.mark.asyncio
async def test_non_english_garbage_blocked(session, monkeypatch):
    seed_registry(session)
    monkeypatch.setattr(mode_execution_service, "_llm_manager", GarbageManager())
    with pytest.raises(ModeExecutionError):
        await mode_execution_service.run(
            session=session,
            tier=PromptTierEnum.FREE,
            mode=PromptModeEnum.SOLVE,
            question_payload={"problem": "x+1=2"},
            context_payload={},
            runtime_hints={},
            request_id=str(uuid.uuid4()),
        )
