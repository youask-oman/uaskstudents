import os
from typing import Any, Dict, Optional

import httpx

from app.services.llm.clients import LLMProviderError, OllamaClient, OpenAIClient


_SUPPORTED_PROVIDERS = {"openai", "ollama"}
_REQUIRED_OPENAI_MODEL = "gpt-5-mini"


def _default_provider() -> str:
    return "openai"


def _default_fallback_enabled() -> bool:
    return False


def _env_true(name: str, default: str = "false") -> bool:
    return (os.environ.get(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def _openai_compat_mode_enabled() -> bool:
    return _env_true("OPENAI_COMPAT_MODE")


def get_configured_openai_model() -> str:
    model = (os.environ.get("OPENAI_MODEL_DEFAULT") or "").strip()
    if not model:
        raise RuntimeError("OPENAI_MODEL_DEFAULT is required")
    if not _openai_compat_mode_enabled() and model != _REQUIRED_OPENAI_MODEL:
        raise RuntimeError(f"OPENAI_MODEL_DEFAULT must be '{_REQUIRED_OPENAI_MODEL}', got '{model}'")
    return model


def get_configured_ollama_model(tier: Optional[str] = None) -> str:
    tier_norm = (tier or "").strip().upper()
    if tier_norm == "FINAL":
        model = (os.environ.get("OLLAMA_MODEL_FINAL") or "").strip()
        if model:
            return model
    model = (os.environ.get("OLLAMA_MODEL") or "Qwen2.5-Math-7B-Instruct-Q4_K_M:latest").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL is required")
    return model


class LLMManager:
    def __init__(self):
        configured_provider = (os.environ.get("LLM_PROVIDER") or _default_provider()).strip().lower()
        if configured_provider and configured_provider not in _SUPPORTED_PROVIDERS:
            raise RuntimeError("LLM_PROVIDER must be one of: openai, ollama")
        self.primary_provider = configured_provider or _default_provider()
        self.fallback_enabled = _default_fallback_enabled()
        self._clients: Dict[str, Any] = {}
        self.last_error: Dict[str, Dict[str, Any]] = {}

    def get_provider_chain(self) -> list:
        return [self.primary_provider]

    def get_fallback_provider(self) -> Optional[str]:
        return None

    def get_client(self, provider: str):
        provider = (provider or "").strip().lower()
        if provider not in _SUPPORTED_PROVIDERS:
            raise LLMProviderError(f"Unknown LLM provider: {provider}", provider=provider)

        if provider in self._clients:
            return self._clients[provider]

        if provider == "openai":
            compat_mode = _openai_compat_mode_enabled()
            client = OpenAIClient(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL"),
                timeout_seconds=int((os.environ.get("OPENAI_TIMEOUT_SECONDS") or "60").strip()),
                default_model=get_configured_openai_model(),
                allow_non_gpt5_model=compat_mode,
                allow_missing_api_key=compat_mode,
            )
        else:
            default_max_tokens_raw = (os.environ.get("OLLAMA_MAX_TOKENS") or "").strip()
            default_max_tokens = int(default_max_tokens_raw) if default_max_tokens_raw else None
            client = OllamaClient(
                base_url=(os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip(),
                default_model=get_configured_ollama_model(),
                timeout_seconds=int((os.environ.get("OLLAMA_TIMEOUT_SECONDS") or "60").strip()),
                connect_timeout_seconds=int((os.environ.get("OLLAMA_CONNECT_TIMEOUT_SECONDS") or "5").strip()),
                default_temperature=float((os.environ.get("OLLAMA_TEMPERATURE") or "0.2").strip()),
                default_num_ctx=int((os.environ.get("OLLAMA_NUM_CTX") or "4096").strip()),
                default_max_tokens=default_max_tokens,
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
        model = (os.environ.get("OPENAI_MODEL_DEFAULT") or "").strip()
        compat_mode = _openai_compat_mode_enabled()
        result = {
            "configured": bool(model and (api_key or compat_mode)),
            "base_url": base_url,
            "model": model,
            "compat_mode": compat_mode,
            "ok": False,
        }
        if not api_key and not compat_mode:
            result["error"] = "OPENAI_API_KEY not configured"
            return result
        if not model:
            result["error"] = "OPENAI_MODEL_DEFAULT not configured"
            return result
        if not compat_mode and model != _REQUIRED_OPENAI_MODEL:
            result["error"] = f"OPENAI_MODEL_DEFAULT must be '{_REQUIRED_OPENAI_MODEL}'"
            return result
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                result["ok"] = resp.status_code == 200
                if not result["ok"]:
                    result["error"] = f"status={resp.status_code}"
        except Exception as exc:
            result["error"] = str(exc).strip() or repr(exc)
        return result

    async def check_ollama(self) -> Dict[str, Any]:
        base_url = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip().rstrip("/")
        model = get_configured_ollama_model()
        final_model = get_configured_ollama_model("FINAL")
        timeout = float((os.environ.get("OLLAMA_CONNECT_TIMEOUT_SECONDS") or "5").strip())
        result = {
            "configured": bool(base_url and model),
            "base_url": base_url,
            "model": model,
            "final_model": final_model,
            "ok": False,
            "model_present": False,
            "final_model_present": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code != 200:
                    result["error"] = f"status={resp.status_code}"
                    return result
                payload = resp.json()
                models = payload.get("models") or []
                names = {str(m.get("name") or "") for m in models if isinstance(m, dict)}
                result["model_present"] = model in names
                result["final_model_present"] = final_model in names
                result["ok"] = result["model_present"] and result["final_model_present"]
                if not result["ok"]:
                    missing = []
                    if not result["model_present"]:
                        missing.append(model)
                    if not result["final_model_present"]:
                        missing.append(final_model)
                    result["error"] = f"model(s) not found: {', '.join(missing)}"
        except Exception as exc:
            result["error"] = str(exc).strip() or repr(exc)
        return result

    def reset_circuit_breaker(self, provider: str) -> Dict[str, Any]:
        provider_key = (provider or "").strip().lower()
        if provider_key != "openai":
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
        if provider_key != "openai":
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
