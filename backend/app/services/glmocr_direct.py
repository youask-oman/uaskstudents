from __future__ import annotations

import base64
import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import httpx

from app.services.glmocr_prompts import (
    GLMOCR_MEASUREMENT_RECOVERY_PROMPT,
    GLMOCR_TRANSCRIBE_PROMPT,
)


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


def _looks_like_measurements_missing(text: str) -> bool:
    src = (text or "").lower()
    if not src:
        return True
    mentions_figure = ("figure" in src) or ("diagram" in src) or ("silo" in src) or ("volume" in src)
    has_choices = bool(("a)" in src and "b)" in src) or ("a " in src and "b " in src and "c " in src))
    has_unit_measurement = bool(re.search(r"\b\d+(?:\.\d+)?\s*(ft|cm|mm|m|in|inch|inches)\b", src))
    return bool(mentions_figure and has_choices and not has_unit_measurement)


def _merge_measurement_lines(base_text: str, recovery_text: str) -> str:
    base = (base_text or "").strip()
    recovery = (recovery_text or "").strip()
    if not recovery:
        return base
    base_lines = [line.strip() for line in base.splitlines() if line.strip()]
    seen = {line.lower() for line in base_lines}
    added: list[str] = []
    for line in recovery.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        added.append(cleaned)
    if not added:
        return base
    if not base:
        return "\n".join(added)
    return f"{base}\n\nFigure measurements:\n" + "\n".join(added)


async def _ollama_generate_once(
    *,
    client: httpx.AsyncClient,
    url: str,
    request_id: str,
    prompt: str,
    image_bytes: bytes,
) -> httpx.Response:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [_to_base64(image_bytes)],
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
    return await client.post(url, json=payload, headers=headers)


async def run_glmocr_prompt(
    *,
    image_bytes: bytes,
    request_id: str,
    prompt: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/api/generate"
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
            prompt_preview = " ".join(str(prompt or "").split())[:220]
            logger.info(
                "glmocr_prompt_start request_id=%s attempt=%s model=%s base_url=%s image_bytes=%s filename=%s prompt_preview=%s",
                request_id,
                attempt,
                OLLAMA_MODEL,
                OLLAMA_BASE_URL,
                len(image_bytes),
                filename or "",
                prompt_preview,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await _ollama_generate_once(
                    client=client,
                    url=url,
                    request_id=request_id,
                    prompt=prompt,
                    image_bytes=image_bytes,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                if resp.status_code >= 400:
                    body = resp.text[:1200]
                    last_error = f"status={resp.status_code} body={body}"
                    logger.warning(
                        "glmocr_prompt_failed request_id=%s attempt=%s latency_ms=%s err=%s filename=%s",
                        request_id,
                        attempt,
                        latency_ms,
                        last_error,
                        filename or "",
                    )
                    continue
                data = resp.json()
                response_text = str(data.get("response") or "")
                logger.info(
                    "glmocr_prompt_ok request_id=%s attempt=%s latency_ms=%s filename=%s",
                    request_id,
                    attempt,
                    latency_ms,
                    filename or "",
                )
                return {"response_text": response_text, "raw_response": data, "latency_ms": latency_ms}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "glmocr_prompt_exception request_id=%s attempt=%s err=%s filename=%s",
                request_id,
                attempt,
                last_error,
                filename or "",
            )
            if attempt < OLLAMA_RETRIES:
                await _sleep_backoff(attempt)
    raise RuntimeError(f"Ollama generate failed after retries: {last_error}")


async def parse_image_with_ollama_generate(
    image_bytes: bytes,
    *,
    request_id: str,
    mime_type: str = "image/png",
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    del mime_type
    primary = await run_glmocr_prompt(
        image_bytes=image_bytes,
        request_id=request_id,
        prompt=GLMOCR_TRANSCRIBE_PROMPT,
        filename=filename,
    )
    response_text = str(primary.get("response_text") or "")
    recovery_used = False
    if _looks_like_measurements_missing(response_text):
        recovery_used = True
        recovered = await run_glmocr_prompt(
            image_bytes=image_bytes,
            request_id=f"{request_id}-measurements",
            prompt=GLMOCR_MEASUREMENT_RECOVERY_PROMPT,
            filename=filename,
        )
        response_text = _merge_measurement_lines(response_text, str(recovered.get("response_text") or ""))

    parsed_json = _safe_json_parse(response_text)
    return {
        "markdown_result": response_text,
        "json_result": parsed_json,
        "backend_used": "ollama_generate",
        "warnings": (["MEASUREMENT_RECOVERY_USED"] if recovery_used else []),
        "raw_response": primary.get("raw_response"),
    }


async def _sleep_backoff(attempt: int) -> None:
    delay = min(0.5 * attempt, 1.5)
    await asyncio.sleep(delay)
