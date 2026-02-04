import os
from typing import Any, Dict, Optional

import httpx

from app.services.llm.clients import LLMProviderError, OpenAIClient


_REQUIRED_OPENAI_PROVIDER = "openai"


def _default_provider() -> str:
    return _REQUIRED_OPENAI_PROVIDER


def _default_fallback_enabled() -> bool:
    return False


def get_configured_openai_model() -> str:
    model = (os.environ.get("OPENAI_MODEL_DEFAULT") or "").strip()
    if not model:
        raise RuntimeError("OPENAI_MODEL_DEFAULT is required")
    return model


class LLMManager:
    def __init__(self):
        configured_provider = (os.environ.get("LLM_PROVIDER") or _default_provider()).strip().lower()
        if configured_provider and configured_provider != _REQUIRED_OPENAI_PROVIDER:
            raise RuntimeError("Only LLM_PROVIDER=openai is supported")
        self.primary_provider = _REQUIRED_OPENAI_PROVIDER
        self.fallback_enabled = _default_fallback_enabled()
        self._clients: Dict[str, Any] = {}
        self.last_error: Dict[str, Dict[str, Any]] = {}

    def get_provider_chain(self) -> list:
        return [self.primary_provider]

    def get_fallback_provider(self) -> Optional[str]:
        return None

    def get_client(self, provider: str):
        provider = (provider or "").strip().lower()
        if provider != _REQUIRED_OPENAI_PROVIDER:
            raise LLMProviderError(f"Unknown LLM provider: {provider}", provider=provider)

        if provider in self._clients:
            return self._clients[provider]

        client = OpenAIClient(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            timeout_seconds=int((os.environ.get("OPENAI_TIMEOUT_SECONDS") or "60").strip()),
            default_model=get_configured_openai_model(),
        )
        self._clients[provider] = client
        return client

    def note_error(self, provider: str, error: Exception) -> None:
        message = str(error).strip() or repr(error)
        error_payload: Dict[str, Any] = {
            "exception_class": error.__class__.__name__,
            "message": message,
        }
        if isinstance(error, LLMProviderError) and error.details:
            error_payload["details"] = error.details
        self.last_error[provider] = error_payload

    async def check_openai(self) -> Dict[str, Any]:
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model = os.environ.get("OPENAI_MODEL_DEFAULT")
        result = {
            "configured": bool(api_key and model),
            "base_url": base_url,
            "model": model,
            "ok": False,
        }
        if not api_key:
            result["error"] = "OPENAI_API_KEY not configured"
            return result
        if not model:
            result["error"] = "OPENAI_MODEL_DEFAULT not configured"
            return result
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                result["ok"] = resp.status_code == 200
                if not result["ok"]:
                    result["error"] = f"status={resp.status_code}"
        except Exception as exc:
            result["error"] = str(exc).strip() or repr(exc)
        return result

    def reset_circuit_breaker(self, provider: str) -> Dict[str, Any]:
        provider_key = (provider or "").strip().lower()
        if provider_key != _REQUIRED_OPENAI_PROVIDER:
            raise LLMProviderError(
                f"Provider '{provider_key}' is not supported.",
                provider=provider_key,
            )
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
        provider_key = (provider or "").strip().lower()
        if provider_key != _REQUIRED_OPENAI_PROVIDER:
            return {"provider": provider_key, "available": False}
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
