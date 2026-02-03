import httpx
import pytest

from app.main import _enforce_ollama_model_availability
from app.services.llm import manager as llm_manager_module


def test_ollama_client_uses_configured_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "mightykatun/qwen2.5-math:7b")
    monkeypatch.setattr(llm_manager_module, "detect_ollama_base_url", lambda _env: "http://ollama.local")
    monkeypatch.setattr(llm_manager_module, "build_candidate_urls", lambda _env: ["http://ollama.local"])
    manager = llm_manager_module.LLMManager()
    client = manager.get_client("ollama")
    assert client.model == "mightykatun/qwen2.5-math:7b"


def test_check_ollama_sync_parses_tags_for_expected_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "mightykatun/qwen2.5-math:7b")
    monkeypatch.setattr(llm_manager_module, "detect_ollama_base_url", lambda _env: "http://ollama.local")
    monkeypatch.setattr(llm_manager_module, "is_ollama_alive", lambda _url: True)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            assert url == "http://ollama.local/api/tags"
            return httpx.Response(
                200,
                json={"models": [{"name": "mightykatun/qwen2.5-math:7b"}, {"name": "qwen2.5vl:3b"}]},
            )

    monkeypatch.setattr(llm_manager_module.httpx, "Client", FakeClient)
    manager = llm_manager_module.LLMManager()
    result = manager.check_ollama_sync(timeout_seconds=1.0)
    assert result["reachable"] is True
    assert result["expected_model"] == "mightykatun/qwen2.5-math:7b"
    assert result["expected_model_available"] is True


def test_startup_check_fails_fast_in_prod_when_model_missing(monkeypatch):
    class FakeManager:
        def check_ollama_sync(self, timeout_seconds=2.0):
            del timeout_seconds
            return {
                "base_url": "http://ollama.local",
                "reachable": True,
                "expected_model": "mightykatun/qwen2.5-math:7b",
                "expected_model_available": False,
                "models": ["qwen2.5vl:3b"],
            }

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        _enforce_ollama_model_availability(FakeManager())
