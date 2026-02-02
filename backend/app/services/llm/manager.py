import asyncio
import ipaddress
import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx

from app.services.llm.clients import LLMProviderError, OpenAIClient, OllamaClient


_RESOLVED_OLLAMA_BASE_URL: Optional[str] = None


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


def _detect_container_runtime() -> bool:
    if os.environ.get("RUNNING_IN_DOCKER", "").lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("CONTAINER", "").lower() in {"1", "true", "yes"}:
        return True
    return os.path.exists("/.dockerenv")


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _looks_like_localhost(url: str) -> bool:
    lowered = url.lower()
    return "://localhost" in lowered or "://127.0.0.1" in lowered


def _read_resolv_nameserver_ip() -> Optional[str]:
    resolv_path = "/etc/resolv.conf"
    if not os.path.exists(resolv_path):
        return None

    try:
        with open(resolv_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("nameserver "):
                    continue
                candidate = line.split(" ", 1)[1].strip()
                try:
                    ip_obj = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                if ip_obj.is_loopback:
                    continue
                return candidate
    except OSError:
        return None
    return None


def _probe_ollama_tags_sync(base_url: str, timeout_seconds: float = 2.0) -> Tuple[bool, Optional[Dict[str, Any]]]:
    url = f"{_normalize_url(base_url)}/api/tags"
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = client.get(url)
            if response.status_code != 200:
                return False, {
                    "exception_class": "HTTPStatus",
                    "message": f"status={response.status_code}",
                    "base_url": _normalize_url(base_url),
                }
            return True, None
    except Exception as exc:
        message = str(exc).strip() or repr(exc)
        return False, {
            "exception_class": exc.__class__.__name__,
            "message": message,
            "base_url": _normalize_url(base_url),
        }


def resolve_ollama_base_url() -> str:
    global _RESOLVED_OLLAMA_BASE_URL

    explicit = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if explicit:
        resolved = _normalize_url(explicit)
        if _detect_container_runtime() and _looks_like_localhost(resolved):
            logging.getLogger("uvicorn").warning(
                "OLLAMA_BASE_URL resolves to localhost inside a container. "
                "Use the WSL IP (for example http://172.26.x.x:11434) or host.docker.internal."
            )
        return resolved

    if _RESOLVED_OLLAMA_BASE_URL:
        return _RESOLVED_OLLAMA_BASE_URL

    if not _detect_container_runtime():
        _RESOLVED_OLLAMA_BASE_URL = "http://localhost:11434"
        return _RESOLVED_OLLAMA_BASE_URL

    candidates = []
    nameserver_ip = _read_resolv_nameserver_ip()
    if nameserver_ip:
        candidates.append(f"http://{nameserver_ip}:11434")
    candidates.append("http://host.docker.internal:11434")

    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        normalized = _normalize_url(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered_candidates.append(normalized)

    for candidate in ordered_candidates:
        reachable, _ = _probe_ollama_tags_sync(candidate, timeout_seconds=2.0)
        if reachable:
            _RESOLVED_OLLAMA_BASE_URL = candidate
            return _RESOLVED_OLLAMA_BASE_URL

    _RESOLVED_OLLAMA_BASE_URL = ordered_candidates[0] if ordered_candidates else "http://localhost:11434"
    if _looks_like_localhost(_RESOLVED_OLLAMA_BASE_URL):
        logging.getLogger("uvicorn").warning(
            "Auto-resolved Ollama base URL is localhost in container mode; this is usually unreachable."
        )
    return _RESOLVED_OLLAMA_BASE_URL


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
            base_url = resolve_ollama_base_url()
            client = OllamaClient(
                base_url=base_url,
                model=os.environ.get("OLLAMA_MODEL_DEFAULT", "mightykatun/qwen2.5-math:7b"),
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
            error_payload["base_url"] = resolve_ollama_base_url()
        if isinstance(error, LLMProviderError) and error.details:
            error_payload["details"] = error.details
            if "base_url" not in error_payload and isinstance(error.details, dict):
                base_url = error.details.get("base_url")
                if base_url:
                    error_payload["base_url"] = base_url
        self.last_error[provider] = error_payload

    async def check_ollama(self) -> Dict[str, Any]:
        base_url = resolve_ollama_base_url()
        result = {
            "configured": bool(os.environ.get("OLLAMA_BASE_URL", "").strip()),
            "resolved_base_url": base_url,
            "base_url": base_url,
            "reachable": False,
            "ok": False,
            "models": [],
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    result["reachable"] = True
                    result["ok"] = True
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    result["models"] = models
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
        base_url = resolve_ollama_base_url()
        reachable, error = _probe_ollama_tags_sync(base_url, timeout_seconds=timeout_seconds)
        result = {"base_url": base_url, "reachable": reachable}
        if error:
            result["error"] = error
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
