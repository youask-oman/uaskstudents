import json

import httpx
import pytest

from app.services.llm.clients import (
    OllamaClient,
    build_ollama_chat_payload,
)


def test_build_ollama_chat_payload():
    payload = build_ollama_chat_payload(
        model="qwen",
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
        options={"temperature": 0.2, "top_p": 0.9, "num_predict": 100},
        keep_alive="5m",
    )
    assert payload["model"] == "qwen"
    assert payload["stream"] is False
    assert payload["options"]["num_predict"] == 100
    assert payload["keep_alive"] == "5m"


@pytest.mark.asyncio
async def test_ollama_chat_response_parsing():
    def handler(request: httpx.Request) -> httpx.Response:
        data = {"message": {"content": "{\"ok\": true}"}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    client = OllamaClient(
        base_url="http://ollama.local",
        model="qwen",
        timeout_seconds=5,
        max_retries=0,
        keep_alive=None,
        temperature=0.2,
        top_p=0.9,
        context_tokens=None,
        transport=transport,
    )

    resp = await client.generate(
        messages=[{"role": "user", "content": "Solve 2+2"}],
        system_prompt=None,
        prompt=None,
        json_schema=None,
        max_tokens=100,
        temperature=None,
        stream=False,
        request_id="test",
    )
    assert json.loads(resp.content)["ok"] is True


@pytest.mark.asyncio
async def test_ollama_retry_on_500():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500, json={"error": "fail"})
        return httpx.Response(200, json={"message": {"content": "{\"ok\": true}"}})

    transport = httpx.MockTransport(handler)
    client = OllamaClient(
        base_url="http://ollama.local",
        model="qwen",
        timeout_seconds=5,
        max_retries=1,
        keep_alive=None,
        temperature=0.2,
        top_p=0.9,
        context_tokens=None,
        transport=transport,
    )

    resp = await client.generate(
        messages=[{"role": "user", "content": "Solve 2+2"}],
        system_prompt=None,
        prompt=None,
        json_schema=None,
        max_tokens=100,
        temperature=None,
        stream=False,
        request_id="test",
    )
    assert json.loads(resp.content)["ok"] is True
    assert calls["count"] == 2
