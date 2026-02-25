from __future__ import annotations

import base64
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger(__name__)


def _default_ollama_base_url() -> str:
    if os.path.exists("/.dockerenv"):
        return "http://host.docker.internal:11434"
    return "http://localhost:11434"


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", _default_ollama_base_url()).rstrip("/")
OLLAMA_MODEL = os.getenv("GLMOCR_MODEL", "glm-ocr:latest")
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(os.getenv("GLMOCR_OLLAMA_CONNECT_TIMEOUT_SECONDS", "5"))
OLLAMA_READ_TIMEOUT_SECONDS = float(os.getenv("GLMOCR_OLLAMA_READ_TIMEOUT_SECONDS", "120"))
OLLAMA_RETRIES = max(1, int(os.getenv("GLMOCR_OLLAMA_RETRIES", "2")))


def _to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def _safe_json_parse(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"raw_text": raw}


async def parse_image_with_ollama_generate(
    image_bytes: bytes,
    *,
    request_id: str,
    mime_type: str = "image/png",
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    del mime_type
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Text Recognition:",
        "images": [_to_base64(image_bytes)],
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
    timeout = httpx.Timeout(
        connect=OLLAMA_CONNECT_TIMEOUT_SECONDS,
        read=OLLAMA_READ_TIMEOUT_SECONDS,
        write=30.0,
        pool=OLLAMA_CONNECT_TIMEOUT_SECONDS,
    )

    last_error: Optional[str] = None
    for attempt in range(1, OLLAMA_RETRIES + 1):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if resp.status_code >= 400:
                body = resp.text[:1200]
                last_error = f"status={resp.status_code} body={body}"
                logger.warning(
                    "glmocr_ollama_generate_failed request_id=%s attempt=%s latency_ms=%s err=%s filename=%s",
                    request_id,
                    attempt,
                    latency_ms,
                    last_error,
                    filename or "",
                )
                continue

            data = resp.json()
            response_text = str(data.get("response") or "")
            parsed_json = _safe_json_parse(response_text)
            logger.info(
                "glmocr_ollama_generate_ok request_id=%s attempt=%s latency_ms=%s filename=%s",
                request_id,
                attempt,
                latency_ms,
                filename or "",
            )
            return {
                "markdown_result": response_text,
                "json_result": parsed_json,
                "backend_used": "ollama_generate",
                "warnings": [],
                "raw_response": data,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "glmocr_ollama_generate_exception request_id=%s attempt=%s err=%s filename=%s",
                request_id,
                attempt,
                last_error,
                filename or "",
            )
            if attempt < OLLAMA_RETRIES:
                await _sleep_backoff(attempt)

    raise RuntimeError(f"Ollama generate failed after retries: {last_error}")


async def _sleep_backoff(attempt: int) -> None:
    delay = min(0.5 * attempt, 1.5)
    await asyncio.sleep(delay)
