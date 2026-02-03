import asyncio
import os
from typing import Any, Dict, Optional

import httpx

from app.services.llm.clients import LLMProviderError, OpenAIClient, OllamaClient
from app.services.ollama import (
    build_candidate_urls,
    detect_ollama_base_url,
    get_last_tried_candidates,
    is_ollama_alive,
)

OLLAMA_REQUIRED_MODEL = "mightykatun/qwen2.5-math:7b"


def _is_production() -> bool:
    for key in ("APP_ENV", "ENV", "ENVIRONMENT", "NODE_ENV"):
        val = os.environ.get(key)
        if val and val.lower() in {"prod", "production"}:
            return True
    return False


def _default_provider() -> str:
    return "openai" if _is_production() else "ollama"


def _default_fallback_enabled() -> bool:
    return not _is_production()


def get_configured_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", OLLAMA_REQUIRED_MODEL)


def _resolve_or_raise_ollama_base_url() -> str:
    env_url = os.environ.get("OLLAMA_BASE_URL")
    resolved = detect_ollama_base_url(env_url)
    if resolved:
        return resolved
    tried = get_last_tried_candidates() or build_candidate_urls(env_url)
    raise RuntimeError(
        "Cannot reach Ollama. Set OLLAMA_BASE_URL or ensure Ollama is reachable. "
        f"Tried: {', '.join(tried)}"
    )


class LLMManager:
    # Semaphore for throttling concurrent Ollama requests
    _ollama_semaphore: asyncio.Semaphore = None
    OLLAMA_MAX_CONCURRENT = int(os.environ.get("OLLAMA_MAX_CONCURRENT", "2"))

    def __init__(self):
        self.primary_provider = os.environ.get("LLM_PROVIDER", _default_provider()).lower()
        self.fallback_enabled = os.environ.get("LLM_FALLBACK_ENABLED", str(_default_fallback_enabled())).lower() in {
            "1",
            "true",
            "yes",
        }
        self._clients: Dict[str, Any] = {}
        self.last_error: Dict[str, Dict[str, Any]] = {}
        
        # Initialize semaphore lazily
        if LLMManager._ollama_semaphore is None:
            LLMManager._ollama_semaphore = asyncio.Semaphore(self.OLLAMA_MAX_CONCURRENT)

    def get_provider_chain(self) -> list:
        providers = [self.primary_provider]
        fallback = self.get_fallback_provider()
        if self.fallback_enabled and fallback:
            providers.append(fallback)
        return providers

    def get_fallback_provider(self) -> Optional[str]:
        if self.primary_provider == "ollama":
            return "openai"
        if self.primary_provider == "openai":
            return "ollama"
        return None

    async def acquire_ollama_slot(self):
        """Acquire a slot for Ollama request (for throttling)."""
        if LLMManager._ollama_semaphore:
            await LLMManager._ollama_semaphore.acquire()

    def release_ollama_slot(self):
        """Release Ollama request slot."""
        if LLMManager._ollama_semaphore:
            LLMManager._ollama_semaphore.release()

    def get_client(self, provider: str):
        provider = provider.lower()
        if provider in self._clients:
            return self._clients[provider]

        if provider == "openai":
            client = OpenAIClient(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL"),
                timeout_seconds=int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "60")),
                default_model=os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
            )
        elif provider == "ollama":
            env_url = os.environ.get("OLLAMA_BASE_URL")
            base_url = _resolve_or_raise_ollama_base_url()
            base_urls = build_candidate_urls(env_url)
            client = OllamaClient(
                base_url=base_url,
                base_urls=base_urls,
                model=get_configured_ollama_model(),
                timeout_seconds=int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30")),
                max_retries=int(os.environ.get("OLLAMA_MAX_RETRIES", "1")),
                keep_alive=os.environ.get("OLLAMA_KEEPALIVE", "5m"),
                temperature=float(os.environ.get("OLLAMA_TEMPERATURE", "0.1")),
                top_p=float(os.environ.get("OLLAMA_TOP_P", "0.9")),
                context_tokens=int(os.environ.get("OLLAMA_CONTEXT_TOKENS")) if os.environ.get("OLLAMA_CONTEXT_TOKENS") else None,
            )
        else:
            raise LLMProviderError(f"Unknown LLM provider: {provider}", provider=provider)

        self._clients[provider] = client
        return client

    def note_error(self, provider: str, error: Exception) -> None:
        message = str(error).strip() or repr(error)
        error_payload: Dict[str, Any] = {
            "exception_class": error.__class__.__name__,
            "message": message,
        }
        if provider == "ollama":
            error_payload["base_url"] = detect_ollama_base_url(os.environ.get("OLLAMA_BASE_URL"))
        if isinstance(error, LLMProviderError) and error.details:
            error_payload["details"] = error.details
            if "base_url" not in error_payload and isinstance(error.details, dict):
                base_url = error.details.get("base_url")
                if base_url:
                    error_payload["base_url"] = base_url
        self.last_error[provider] = error_payload

    async def check_ollama(self) -> Dict[str, Any]:
        env_url = os.environ.get("OLLAMA_BASE_URL")
        base_url = detect_ollama_base_url(env_url)
        expected_model = get_configured_ollama_model()
        tried = get_last_tried_candidates() or build_candidate_urls(env_url)
        result = {
            "configured": bool(os.environ.get("OLLAMA_BASE_URL", "").strip()),
            "resolved_base_url": base_url,
            "base_url": base_url,
            "reachable": False,
            "ok": False,
            "models": [],
            "expected_model": expected_model,
            "expected_model_available": False,
            "tried": tried,
        }
        if not base_url:
            result["error"] = {
                "exception_class": "RuntimeError",
                "message": "Cannot reach Ollama. Set OLLAMA_BASE_URL or ensure Ollama is reachable.",
                "tried": tried,
            }
            return result
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    result["reachable"] = True
                    result["ok"] = True
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    result["models"] = models
                    result["expected_model_available"] = expected_model in models
                else:
                    result["error"] = {
                        "exception_class": "HTTPStatus",
                        "message": f"status={resp.status_code}",
                        "base_url": base_url,
                    }
        except Exception as exc:
            result["error"] = {
                "exception_class": exc.__class__.__name__,
                "message": str(exc).strip() or repr(exc),
                "base_url": base_url,
            }
        return result

    def check_ollama_sync(self, timeout_seconds: float = 2.0) -> Dict[str, Any]:
        env_url = os.environ.get("OLLAMA_BASE_URL")
        base_url = detect_ollama_base_url(env_url)
        tried = get_last_tried_candidates() or build_candidate_urls(env_url)
        expected_model = get_configured_ollama_model()
        reachable = bool(base_url and is_ollama_alive(base_url))
        result = {
            "base_url": base_url,
            "reachable": reachable,
            "tried": tried,
            "models": [],
            "expected_model": expected_model,
            "expected_model_available": False,
        }
        if not reachable:
            result["error"] = {
                "exception_class": "RuntimeError",
                "message": "Cannot reach Ollama. Set OLLAMA_BASE_URL or ensure Ollama is reachable.",
                "tried": tried,
            }
            return result
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
                resp = client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    result["models"] = models
                    result["expected_model_available"] = expected_model in models
                else:
                    result["error"] = {
                        "exception_class": "HTTPStatus",
                        "message": f"status={resp.status_code}",
                        "base_url": base_url,
                    }
        except Exception as exc:
            result["error"] = {
                "exception_class": exc.__class__.__name__,
                "message": str(exc).strip() or repr(exc),
                "base_url": base_url,
            }
        return result

    async def check_openai(self) -> Dict[str, Any]:
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        result = {"configured": bool(api_key), "base_url": base_url, "ok": False}
        if not api_key:
            return result
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                result["ok"] = resp.status_code == 200
        except Exception as e:
            result["error"] = str(e)[:200]
        return result

    def reset_circuit_breaker(self, provider: str) -> Dict[str, Any]:
        provider_key = provider.lower()
        client = self.get_client(provider_key)
        if not hasattr(client, "reset_circuit_breaker"):
            raise LLMProviderError(
                f"Provider '{provider_key}' does not expose a circuit breaker.",
                provider=provider_key,
            )
        client.reset_circuit_breaker()
        self.last_error.pop(provider_key, None)
        return {"provider": provider_key, "reset": True}

    def get_circuit_breaker_state(self, provider: str) -> Dict[str, Any]:
        provider_key = provider.lower()
        client = self.get_client(provider_key)
        if not hasattr(client, "get_circuit_breaker_state"):
            return {"provider": provider_key, "available": False}
        state = client.get_circuit_breaker_state()
        return {"provider": provider_key, "available": True, **state}


_manager_instance: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = LLMManager()
    return _manager_instance
