from __future__ import annotations

import json
import os

import httpx
import pytest

from app.services.llm.clients import LLMProviderError, OllamaClient
from app.services.llm.manager import LLMManager


def _factory_with_transport(transport: httpx.BaseTransport):
    def _factory(timeout: httpx.Timeout):
        return httpx.AsyncClient(transport=transport, timeout=timeout)

    return _factory


@pytest.mark.asyncio
async def test_ollama_client_generate_success_with_metrics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "qwen25-math7b:latest"
        assert payload["stream"] is False
        assert "prompt" in payload and payload["prompt"]
        return httpx.Response(
            200,
            json={
                "model": "qwen25-math7b:latest",
                "response": '{"final_answer":"42"}',
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 18,
                "eval_count": 9,
                "total_duration": 12000000,
                "eval_duration": 6000000,
            },
        )

    client = OllamaClient(
        base_url="http://localhost:11434",
        default_model="qwen25-math7b:latest",
        timeout_seconds=60,
        connect_timeout_seconds=5,
        default_temperature=0.2,
        default_num_ctx=4096,
        default_max_tokens=None,
        http_client_factory=_factory_with_transport(httpx.MockTransport(handler)),
    )

    resp = await client.generate(
        messages=[{"role": "user", "content": "Solve x+1=2"}],
        system_prompt="You are a math engine",
        prompt=None,
        json_schema={"type": "object"},
        max_tokens=200,
        temperature=None,
        stream=False,
        request_id="test-req-1",
    )

    assert resp.provider == "ollama"
    assert resp.model == "qwen25-math7b:latest"
    assert resp.content == '{"final_answer":"42"}'
    assert resp.usage["input"] == 18
    assert resp.usage["output"] == 9
    assert resp.usage["total"] == 27
    assert resp.payload["ollama_metrics"]["total_duration"] == 12000000


@pytest.mark.asyncio
async def test_ollama_client_model_not_found_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    client = OllamaClient(
        base_url="http://localhost:11434",
        default_model="qwen25-math7b:latest",
        timeout_seconds=60,
        connect_timeout_seconds=5,
        http_client_factory=_factory_with_transport(httpx.MockTransport(handler)),
    )

    with pytest.raises(LLMProviderError) as exc:
        await client.generate(
            messages=[{"role": "user", "content": "hello"}],
            system_prompt=None,
            prompt=None,
            json_schema=None,
            max_tokens=None,
            temperature=None,
            stream=False,
        )

    assert exc.value.provider == "ollama"
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value).lower()


def test_llm_manager_supports_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen25-math7b:latest")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("OLLAMA_TEMPERATURE", "0.2")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    monkeypatch.delenv("OLLAMA_MAX_TOKENS", raising=False)

    mgr = LLMManager()
    assert mgr.primary_provider == "ollama"
    assert mgr.get_provider_chain() == ["ollama"]
    client = mgr.get_client("ollama")
    assert isinstance(client, OllamaClient)


@pytest.mark.asyncio
async def test_ollama_live_connectivity_optional() -> None:
    if os.environ.get("OLLAMA_RUN_LIVE_TESTS", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set OLLAMA_RUN_LIVE_TESTS=1 to run live Ollama connectivity test.")

    manager = LLMManager()
    client = manager.get_client("ollama")
    response = await client.generate(
        messages=[{"role": "user", "content": "Answer with only a number: 21+21"}],
        system_prompt="You are a concise math assistant.",
        prompt=None,
        json_schema=None,
        max_tokens=64,
        temperature=0.0,
        stream=False,
        request_id="ollama-live-connectivity",
    )
    assert response.provider == "ollama"
    assert isinstance(response.content, str) and response.content.strip()
