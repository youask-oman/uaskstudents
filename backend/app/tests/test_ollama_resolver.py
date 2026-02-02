import httpx

from app.services.ollama import ollama_resolver


def test_valid_env_url_selected_when_reachable(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://env-ollama:11434")
    detected = ollama_resolver.detect_ollama_base_url("http://env-ollama:11434")
    assert detected == "http://env-ollama:11434"


def test_invalid_env_url_falls_back_to_candidates(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://localhost:11434")
    detected = ollama_resolver.detect_ollama_base_url("http://1:11434http://localhost:11434")
    assert detected == "http://localhost:11434"


def test_no_candidates_reachable_returns_none(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda _url: False)
    detected = ollama_resolver.detect_ollama_base_url(None)
    assert detected is None


def test_normalization_removes_trailing_slash(monkeypatch):
    ollama_resolver.clear_ollama_url_cache()
    monkeypatch.setattr(ollama_resolver, "is_ollama_alive", lambda url: url == "http://ollama:11434")
    detected = ollama_resolver.detect_ollama_base_url("http://ollama:11434/")
    assert detected == "http://ollama:11434"


def test_is_ollama_alive_uses_tags_endpoint(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            assert url == "http://ollama:11434/api/tags"
            return httpx.Response(200, json={"models": []})

    monkeypatch.setattr(ollama_resolver.httpx, "Client", FakeClient)
    assert ollama_resolver.is_ollama_alive("http://ollama:11434/") is True
