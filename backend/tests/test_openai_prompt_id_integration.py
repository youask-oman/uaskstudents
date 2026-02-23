from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from app.services.llm.clients import OpenAIClient


class _FakeUsage:
    def __init__(self) -> None:
        self.input_tokens = 12
        self.output_tokens = 7
        self.total_tokens = 19
        self.input_token_details = SimpleNamespace(cached_tokens=3)


class _FakeResponse:
    def __init__(self, model: str = "gpt-5-mini") -> None:
        self.model = model
        self.status = "completed"
        self.output_text = '{"ok":true}'
        self.output: List[Any] = []
        self.usage = _FakeUsage()

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return {"id": "resp_123", "model": self.model, "status": self.status}


class _FakeResponses:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.fail_first = fail_first

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            exc = Exception("variables embedding rejected")
            setattr(exc, "status_code", 400)
            raise exc
        return _FakeResponse()


class _FakeOpenAIClient:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.responses = _FakeResponses(fail_first=fail_first)

    def with_options(self, timeout: float | None = None) -> "_FakeOpenAIClient":
        return self


def _make_client(*, fail_first: bool = False) -> OpenAIClient:
    client = OpenAIClient(
        api_key="test-key",
        base_url=None,
        timeout_seconds=30,
        default_model="gpt-5-mini",
    )
    client._client = _FakeOpenAIClient(fail_first=fail_first)  # type: ignore[attr-defined]
    return client


@pytest.mark.asyncio
async def test_prompt_id_call_uses_input_when_no_variables() -> None:
    client = _make_client()
    response = await client.generate(
        messages=[{"role": "user", "content": "Solve x+1=2"}],
        system_prompt=None,
        prompt=None,
        json_schema=None,
        max_tokens=128,
        temperature=0.0,
        stream=False,
        request_id="req-1",
        managed_prompt_id="pmpt_699bd302d0f4819692162fd6066621fc011cbc57e13867cf",
        managed_prompt_version="1",
        managed_prompt_use_latest=False,
        managed_prompt_variables=None,
        managed_prompt_input="Q1: Solve x+1=2",
        prompt_cache_key="solve:SHORT_STEPS:SOLVE:reals:en",
        prompt_cache_retention="24h",
    )

    fake = client._client  # type: ignore[attr-defined]
    assert len(fake.responses.calls) == 1
    sent = fake.responses.calls[0]
    assert sent["prompt"]["id"] == "pmpt_699bd302d0f4819692162fd6066621fc011cbc57e13867cf"
    assert sent["prompt"]["version"] == "1"
    assert isinstance(sent.get("input"), str) and sent["input"] == "Q1: Solve x+1=2"
    assert sent.get("prompt_cache_key") == "solve:SHORT_STEPS:SOLVE:reals:en"
    assert sent.get("prompt_cache_retention") == "24h"
    assert response.payload.get("openai_prompt_id") == "pmpt_699bd302d0f4819692162fd6066621fc011cbc57e13867cf"
    assert response.payload.get("openai_prompt_version") == "1"
    assert response.payload.get("openai_prompt_cache_key") == "solve:SHORT_STEPS:SOLVE:reals:en"
    assert response.payload.get("openai_prompt_cache_retention") == "24h"


@pytest.mark.asyncio
async def test_prompt_id_variables_embedded_then_top_level_fallback() -> None:
    client = _make_client(fail_first=True)
    await client.generate(
        messages=[{"role": "user", "content": "Solve"}],
        system_prompt=None,
        prompt=None,
        json_schema=None,
        max_tokens=64,
        temperature=0.0,
        stream=False,
        request_id="req-2",
        managed_prompt_id="pmpt_699bd302d0f4819692162fd6066621fc011cbc57e13867cf",
        managed_prompt_version="1",
        managed_prompt_use_latest=False,
        managed_prompt_variables={"question": "Solve x+1=2"},
    )

    fake = client._client  # type: ignore[attr-defined]
    assert len(fake.responses.calls) == 2
    first = fake.responses.calls[0]
    second = fake.responses.calls[1]
    assert "variables" in first["prompt"]
    assert first["prompt"]["variables"]["question"] == "Solve x+1=2"
    assert "variables" in second
    assert second["variables"]["question"] == "Solve x+1=2"


@pytest.mark.asyncio
async def test_prompt_id_requires_input_or_variables() -> None:
    client = _make_client()
    with pytest.raises(Exception):
        await client.generate(
            messages=[],
            system_prompt=None,
            prompt=None,
            json_schema=None,
            max_tokens=32,
            temperature=0.0,
            stream=False,
            request_id="req-3",
            managed_prompt_id="pmpt_699bd302d0f4819692162fd6066621fc011cbc57e13867cf",
            managed_prompt_version="1",
            managed_prompt_use_latest=False,
            managed_prompt_variables=None,
            managed_prompt_input=None,
        )
