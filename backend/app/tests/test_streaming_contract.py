import json

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import PromptModeEnum, PromptRoleEnum, PromptTierEnum
from app.prompts.db_loader import load_prompt_bundle
from app.services.llm.clients import LLMStreamResponse
from app.services.prompt_registry_service import prompt_registry_service
from app.services.solver_v3 import SolverV3


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "streaming_contract.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_binding(session: Session) -> None:
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="SYSTEM_PROMPT",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_free_minimal_v1",
        content="DEVELOPER_PROMPT",
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_response_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.FREE,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_free_minimal_v1",
        "youask_math_solver_response_v1",
        "tester",
    )


def test_db_binding_loader_resolves_prompt_and_schema(session: Session):
    _seed_binding(session)
    bundle = load_prompt_bundle(tier="free", mode="solve", session=session)
    assert bundle["system_prompt"] == "SYSTEM_PROMPT"
    assert bundle["developer_prompt"] == "DEVELOPER_PROMPT"
    assert bundle["schema"]["type"] == "object"
    assert bundle["meta"]["binding_id"]
    assert bundle["meta"]["global_system_prompt_id"] == "global_system_prompt_v1"
    assert bundle["meta"]["developer_prompt_id"] == "solve_free_minimal_v1"
    assert bundle["meta"]["output_schema_id"] == "youask_math_solver_response_v1"


class _FakeStreamingClient:
    async def generate_stream(self, **kwargs):
        del kwargs
        yield LLMStreamResponse(content='{"final_answer":"', provider="openai", model="gpt-5-mini", done=False)
        yield LLMStreamResponse(content='ok"}', provider="openai", model="gpt-5-mini", done=False)
        yield LLMStreamResponse(
            content="",
            provider="openai",
            model="gpt-5-mini",
            usage={"input": 1, "output": 2, "total": 3, "cached": None},
            status={"status": "completed"},
            done=True,
        )


class _FakeManager:
    primary_provider = "openai"

    def get_client(self, provider):
        assert provider == "openai"
        return _FakeStreamingClient()


@pytest.mark.asyncio
async def test_solve_stream_async_iterator_contract_no_crash():
    solver = SolverV3()
    solver.client_manager = _FakeManager()

    chunks = []
    async for chunk in solver.solve_stream(
        problem_text="33 + 4 - 9 = 17",
        context="",
        trace=False,
        request_id="r1",
        system_prompt="SYS",
        developer_prompt="DEV",
        json_schema_config={"type": "object"},
        requested_mode="minimal",
    ):
        chunks.append(chunk)

    assert any(c.get("type") == "delta" for c in chunks)
    assert any(c.get("type") == "telemetry" for c in chunks)
    assert not any(c.get("type") == "error" for c in chunks)


@pytest.mark.asyncio
async def test_solve_stream_no_file_fallback_when_prompt_missing():
    solver = SolverV3()
    solver.client_manager = _FakeManager()

    chunks = []
    async for chunk in solver.solve_stream(
        problem_text="1+1",
        context="",
        trace=False,
        request_id="r2",
        system_prompt=None,
        developer_prompt=None,
        json_schema_config={"type": "object"},
        requested_mode="minimal",
    ):
        chunks.append(chunk)

    assert chunks[0]["type"] == "error"
    assert chunks[0]["error"]["code"] == "prompt_binding_missing"
