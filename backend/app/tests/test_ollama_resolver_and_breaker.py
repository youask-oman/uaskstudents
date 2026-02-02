import json

import httpx
import pytest
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel, Session, create_engine

from app.api import PromptRegistryTestRequest, admin_prompt_registry_test, admin_reset_llm_circuit_breaker
from app.models import PromptModeEnum, PromptRoleEnum, PromptTierEnum
from app.services.llm.clients import LLMProviderError, OllamaClient
from app.services.llm import manager as llm_manager_module
from app.services.ollama import ollama_resolver
from app.services.mode_execution_service import mode_execution_service
from app.services.prompt_registry_service import prompt_registry_service


def _seed_minimal_registry(session: Session) -> None:
    prompt_registry_service.update_prompt(
        session,
        "global_system_prompt_v1",
        "GLOBAL",
        None,
        PromptModeEnum.SOLVE,
        PromptRoleEnum.SYSTEM,
        "test",
    )
    prompt_registry_service.update_prompt(
        session,
        "solve_free_minimal_v1",
        "DEV_FREE_SOLVE",
        PromptTierEnum.FREE,
        PromptModeEnum.SOLVE,
        PromptRoleEnum.DEVELOPER,
        "test",
    )
    prompt_registry_service.update_schema(
        session,
        "youask_math_solver_response_v1",
        {
            "type": "object",
            "required": ["answer_text", "steps"],
            "properties": {
                "answer_text": {"type": "string"},
                "steps": {"type": "array"},
            },
        },
        "test",
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.FREE,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_free_minimal_v1",
        "youask_math_solver_response_v1",
        "test",
    )


def _generate_kwargs():
    return {
        "messages": [{"role": "user", "content": "Solve 2+2"}],
        "system_prompt": None,
        "prompt": None,
        "json_schema": None,
        "max_tokens": 100,
        "temperature": None,
        "stream": False,
        "request_id": "test",
    }


def test_resolver_prefers_explicit_env(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://172.26.131.128:11434")
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://172.26.131.128:11434")
    assert ollama_resolver.detect_ollama_base_url("http://172.26.131.128:11434") == "http://172.26.131.128:11434"


def test_resolver_parses_multiple_and_malformed_explicit_urls(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://localhost:11434")
    detected = ollama_resolver.detect_ollama_base_url("http://172.26.131.128:11434http://localhost:11434")
    assert detected == "http://localhost:11434"


def test_resolver_uses_wsl_gateway_candidate(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://host.docker.internal:11434")
    assert ollama_resolver.detect_ollama_base_url(None) == "http://host.docker.internal:11434"


@pytest.mark.asyncio
async def test_health_check_has_meaningful_error(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setattr(llm_manager_module, "detect_ollama_base_url", lambda _env: "http://172.26.131.128:11434")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(llm_manager_module.httpx, "AsyncClient", FakeAsyncClient)
    manager = llm_manager_module.LLMManager()
    result = await manager.check_ollama()

    assert result["reachable"] is False
    assert result["error"]["exception_class"] == "RuntimeError"
    assert "connection refused" in result["error"]["message"]
    assert result["error"]["base_url"] == "http://172.26.131.128:11434"


@pytest.mark.asyncio
async def test_breaker_counts_only_transient_failures():
    def handler_400(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    client_400 = OllamaClient(
        base_url="http://ollama.local",
        model="qwen",
        timeout_seconds=5,
        max_retries=0,
        keep_alive=None,
        temperature=0.1,
        top_p=0.9,
        context_tokens=None,
        transport=httpx.MockTransport(handler_400),
    )

    for _ in range(4):
        with pytest.raises(LLMProviderError):
            await client_400.generate(**_generate_kwargs())

    state_400 = client_400.get_circuit_breaker_state()
    assert state_400["failure_count"] == 0
    assert state_400["open"] is False

    def handler_500(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server down"})

    client_500 = OllamaClient(
        base_url="http://ollama.local",
        model="qwen",
        timeout_seconds=5,
        max_retries=0,
        keep_alive=None,
        temperature=0.1,
        top_p=0.9,
        context_tokens=None,
        transport=httpx.MockTransport(handler_500),
    )

    for _ in range(3):
        with pytest.raises(LLMProviderError):
            await client_500.generate(**_generate_kwargs())

    state_500 = client_500.get_circuit_breaker_state()
    assert state_500["open"] is True
    assert state_500["reset_in_seconds"] >= 0


@pytest.mark.asyncio
async def test_breaker_opens_then_reset_allows_requests_again():
    state = {"fail": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"message": {"content": "{\"ok\": true}"}})

    client = OllamaClient(
        base_url="http://ollama.local",
        model="qwen",
        timeout_seconds=5,
        max_retries=0,
        keep_alive=None,
        temperature=0.1,
        top_p=0.9,
        context_tokens=None,
        transport=httpx.MockTransport(handler),
    )

    for _ in range(3):
        with pytest.raises(LLMProviderError):
            await client.generate(**_generate_kwargs())

    with pytest.raises(LLMProviderError) as exc_info:
        await client.generate(**_generate_kwargs())
    assert "circuit breaker open" in str(exc_info.value).lower()
    assert exc_info.value.status_code == 503
    assert "reset_in_seconds" in exc_info.value.details

    client.reset_circuit_breaker()
    state["fail"] = False
    response = await client.generate(**_generate_kwargs())
    assert json.loads(response.content)["ok"] is True


@pytest.mark.asyncio
async def test_breaker_open_maps_to_api_503(monkeypatch, tmp_path):
    class BreakerOpenClient:
        async def generate(self, **kwargs):
            raise LLMProviderError(
                "Ollama circuit breaker open.",
                provider="ollama",
                status_code=503,
                is_transient=True,
                details={
                    "base_url": "http://172.26.131.128:11434",
                    "reset_in_seconds": 20,
                    "last_failure": {"exception_class": "ConnectError", "message": "refused"},
                },
            )

    class FakeManager:
        def __init__(self):
            self.last_error = {}

        def get_provider_chain(self):
            return ["ollama"]

        def get_client(self, provider):
            return BreakerOpenClient()

        def note_error(self, provider, error):
            self.last_error[provider] = str(error)

    db_path = tmp_path / "breaker_api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_minimal_registry(session)
        monkeypatch.setattr(mode_execution_service, "_llm_manager", FakeManager())
        response = await admin_prompt_registry_test(
            PromptRegistryTestRequest(
                tier="FREE",
                mode="SOLVE",
                question_payload={"problem": "2+2"},
                context_payload={},
                runtime_hints={},
            ),
            session,
        )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["code"] == "LLM_PROVIDER_ERROR"
    assert payload["provider"] == "ollama"
    assert payload["base_url"] == "http://172.26.131.128:11434"


@pytest.mark.asyncio
async def test_reset_endpoint_calls_manager(monkeypatch):
    class FakeManager:
        def __init__(self):
            self.called_with = None

        def reset_circuit_breaker(self, provider):
            self.called_with = provider
            return {"provider": provider, "reset": True}

    fake_manager = FakeManager()
    monkeypatch.setattr("app.api.get_llm_manager", lambda: fake_manager)
    result = await admin_reset_llm_circuit_breaker(provider="ollama")
    assert result["reset"] is True
    assert fake_manager.called_with == "ollama"
