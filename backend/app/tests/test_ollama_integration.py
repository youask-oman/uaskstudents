import os

import httpx
import pytest

from app.services.solver_v3 import SolverV3
from app.services.validation_v3 import validate_response


@pytest.mark.asyncio
async def test_ollama_integration_smoke(monkeypatch):
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.status_code != 200:
                pytest.skip("Ollama not reachable")
    except Exception:
        pytest.skip("Ollama not reachable")

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")

    solver = SolverV3()
    result = await solver.solve("Solve x + 1 = 2", max_output_tokens=400)

    cleaned = {k: v for k, v in result.items() if k not in {"telemetry", "_telemetry", "_timestamp"}}
    validation = validate_response(cleaned, strict=True)
    assert validation.valid
