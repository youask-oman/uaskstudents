import json

import pytest

from app.services.llm.clients import LLMProviderError, LLMResponse
from app.services.solver_v3 import SolverV3


class FakeLLMManager:
    def __init__(self, primary, fallback, clients):
        self.primary_provider = primary
        self._fallback = fallback
        self._clients = clients
        self.fallback_enabled = True
        self.last_error = {}

    def get_provider_chain(self):
        return [self.primary_provider, self._fallback]

    def get_fallback_provider(self):
        return self._fallback

    def get_client(self, provider):
        return self._clients[provider]

    def note_error(self, provider, error):
        self.last_error[provider] = str(error)


class FailingClient:
    async def generate(self, **kwargs):
        raise LLMProviderError("ollama down", provider="ollama", is_transient=True)


class SuccessClient:
    async def generate(self, **kwargs):
        return LLMResponse(
            content=json.dumps({"ok": True}),
            provider="openai",
            model="gpt-4o-mini",
            usage={"input": 1, "output": 1, "total": 2, "cached": None},
            status={"status": "completed", "finish_reason": "stop"},
            payload={},
            attempts=1,
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_fallback_to_openai_when_ollama_fails():
    manager = FakeLLMManager(
        primary="ollama",
        fallback="openai",
        clients={"ollama": FailingClient(), "openai": SuccessClient()},
    )
    solver = SolverV3(llm_manager=manager)

    # Bypass schema validation to focus on fallback path
    solver._check_status_and_validate = lambda data, status, schema, raw_text=None: (True, None, data, [])

    result = await solver.solve("2+2", requested_mode="detailed")
    assert result.get("ok") is True
