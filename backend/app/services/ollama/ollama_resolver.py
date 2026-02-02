import logging
import os
from typing import List, Optional
from urllib.parse import urlparse

import httpx


logger = logging.getLogger("uvicorn")

PROBE_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_PROBE_TIMEOUT_SECONDS", "0.35"))
DEFAULT_OLLAMA_CANDIDATES = [
    "http://ollama:11434",
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://host.docker.internal:11434",
    "http://172.17.0.1:11434",
]

_CACHED_BASE_URL: Optional[str] = None
_CACHED_ENV_VALUE: Optional[str] = None
_LAST_TRIED_CANDIDATES: List[str] = []


def _normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _is_valid_single_url(raw: str) -> bool:
    if not raw:
        return False
    if any(ch.isspace() for ch in raw):
        return False
    lowered = raw.lower()
    first_http = lowered.find("http://")
    first_https = lowered.find("https://")
    if first_http > 0 or first_https > 0:
        return False
    if first_http == -1 and first_https == -1:
        return False
    after_scheme = lowered[8:] if lowered.startswith("https://") else lowered[7:]
    if "http://" in after_scheme or "https://" in after_scheme:
        return False

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True


def build_candidate_urls(env_url: Optional[str]) -> List[str]:
    candidates: List[str] = []
    seen = set()

    def _append(url: str) -> None:
        normalized = _normalize_url(url)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    if env_url and _is_valid_single_url(env_url):
        _append(env_url)
    for candidate in DEFAULT_OLLAMA_CANDIDATES:
        _append(candidate)
    return candidates


def get_last_tried_candidates() -> List[str]:
    return list(_LAST_TRIED_CANDIDATES)


def clear_ollama_url_cache() -> None:
    global _CACHED_BASE_URL, _CACHED_ENV_VALUE, _LAST_TRIED_CANDIDATES
    _CACHED_BASE_URL = None
    _CACHED_ENV_VALUE = None
    _LAST_TRIED_CANDIDATES = []


def is_ollama_alive(url: str) -> bool:
    normalized = _normalize_url(url)
    if not normalized:
        return False
    try:
        with httpx.Client(timeout=httpx.Timeout(PROBE_TIMEOUT_SECONDS)) as client:
            response = client.get(f"{normalized}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


def detect_ollama_base_url(env_url: Optional[str]) -> Optional[str]:
    global _CACHED_BASE_URL, _CACHED_ENV_VALUE, _LAST_TRIED_CANDIDATES

    raw_env = (env_url or "").strip() or None
    if _CACHED_BASE_URL and _CACHED_ENV_VALUE == raw_env:
        return _CACHED_BASE_URL

    if raw_env and not _is_valid_single_url(raw_env):
        logger.warning("Invalid OLLAMA_BASE_URL value ignored: %r", raw_env)

    candidates = build_candidate_urls(raw_env)
    _LAST_TRIED_CANDIDATES = []

    for candidate in candidates:
        _LAST_TRIED_CANDIDATES.append(candidate)
        if is_ollama_alive(candidate):
            _CACHED_BASE_URL = candidate
            _CACHED_ENV_VALUE = raw_env
            if raw_env and _normalize_url(raw_env) == candidate:
                logger.info("Ollama URL selected from OLLAMA_BASE_URL: %s", candidate)
            else:
                logger.info("Ollama URL auto-detected: %s", candidate)
            return candidate

    _CACHED_BASE_URL = None
    _CACHED_ENV_VALUE = raw_env
    logger.warning("Unable to reach Ollama. Tried candidates: %s", ", ".join(_LAST_TRIED_CANDIDATES))
    return None
