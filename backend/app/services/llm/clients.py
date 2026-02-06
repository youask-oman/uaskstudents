import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from app.utils.structured_output_builder import build_openai_structured_output, log_openai_request_trace


class LLMProviderError(Exception):
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        is_transient: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.is_transient = is_transient
        self.details = details or {}


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: Dict[str, Any]
    status: Dict[str, Any]
    payload: Dict[str, Any]
    attempts: int
    latency_ms: int


@dataclass
class LLMStreamResponse:
    content: str
    provider: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    status: Optional[Dict[str, Any]] = None
    latency_ms: int = 0
    done: bool = False


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failure_count = 0
        self.open_until = 0.0
        self.last_failure: Optional[Dict[str, Any]] = None

    def allow_request(self) -> bool:
        if self.open_until == 0.0:
            return True
        if time.time() >= self.open_until:
            self.open_until = 0.0
            self.failure_count = 0
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.open_until = 0.0

    def record_failure(self, reason: Optional[Dict[str, Any]] = None) -> None:
        self.last_failure = reason
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.open_until = time.time() + self.reset_seconds

    def reset(self) -> None:
        self.failure_count = 0
        self.open_until = 0.0
        self.last_failure = None

    def reset_in_seconds(self) -> int:
        if self.open_until <= 0.0:
            return 0
        return max(0, int(self.open_until - time.time()))



def _debug_enabled() -> bool:
    return (os.environ.get("LLM_DEBUG_LOGS") or "").lower() in {"1", "true", "yes"}


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_prompt_preview(text: str, limit: int = 200) -> Dict[str, str]:
    text = text or ""
    return {"preview": text[:limit], "sha256": _hash_text(text)}


def _log_llm(event: str, payload: Dict[str, Any]) -> None:
    if not _debug_enabled():
        return
    logger = logging.getLogger("llm")
    logger.info(json.dumps({"event": event, **payload}))




def _normalize_openai_schema_wrapper(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Normalize DB-provided schema wrappers into the canonical internal shape:
      {"type":"json_schema","name":str,"strict":bool,"schema":{...draft...}}

    Defensive behavior:
    - If a half-wrapper {"schema": {...}} is received, wrap it as name="raw_schema"
      and strict=True, and log a warning. This avoids crashing in production while
      still surfacing the upstream bug.
    - If a chat-completions style wrapper {"type":"json_schema","json_schema":{...}} is received,
      unwrap it into canonical form.
    - If a raw Draft schema is received (has "$schema" or "type"/"properties"), wrap it similarly.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"json_schema must be a dict, got {type(raw)}")

    keys = set(raw.keys())

    # Canonical DB wrapper
    if {"type", "name", "strict", "schema"}.issubset(keys) and raw.get("type") == "json_schema":
        return raw

    # OpenAI chat-completions wrapper variant: {"type":"json_schema","json_schema":{name,strict,schema}}
    if raw.get("type") == "json_schema" and isinstance(raw.get("json_schema"), dict):
        inner = raw["json_schema"]
        return {
            "type": "json_schema",
            "name": inner.get("name", "raw_schema"),
            "strict": bool(inner.get("strict", True)),
            "schema": inner.get("schema", {}),
        }

    # Half-wrapper detected: {"schema": {...}} (THIS IS A BUG UPSTREAM)
    if keys == {"schema"} and isinstance(raw.get("schema"), dict):
        raise ValueError("Half-wrapper schema detected (only 'schema' key). Upstream logic broken. Aborting to prevent silent fallback.")

    # Raw Draft schema
    if "$schema" in raw or raw.get("type") in {"object", "array", "string", "number", "integer", "boolean", "null"} or "properties" in raw:
        return {"type": "json_schema", "name": "raw_schema", "strict": True, "schema": raw}

    # Unknown shape: fail loudly
    raise ValueError(f"Unknown json_schema format. Keys={sorted(keys)}")


class OpenAIClient:
    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout_seconds: int,
        default_model: str,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.default_model = default_model
        self._client = None
        self._breaker = CircuitBreaker(
            failure_threshold=int((os.environ.get("OPENAI_BREAKER_FAILURE_THRESHOLD") or "3").strip()),
            reset_seconds=int((os.environ.get("OPENAI_BREAKER_RESET_SECONDS") or "30").strip()),
        )
        self._last_error_details: Optional[Dict[str, Any]] = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_seconds}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        return {
            "failure_count": self._breaker.failure_count,
            "open": not self._breaker.allow_request(),
            "reset_in_seconds": self._breaker.reset_in_seconds(),
            "last_failure": self._breaker.last_failure or self._last_error_details,
        }

    def reset_circuit_breaker(self) -> None:
        self._breaker.reset()
        self._last_error_details = None

    def _record_failure(self, category: str, exc: Exception, status_code: Optional[int] = None) -> Dict[str, Any]:
        details = {
            "category": category,
            "exception_class": exc.__class__.__name__,
            "message": str(exc).strip() or repr(exc),
        }
        if status_code is not None:
            details["status_code"] = status_code
        self._last_error_details = details
        self._breaker.record_failure(details)
        return details

    async def generate(
        self,
        *,
        messages: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str],
        prompt: Optional[str],
        json_schema: Optional[Dict[str, Any]],
        max_tokens: int,
        temperature: Optional[float],
        stream: bool,
        request_id: Optional[str],
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
    ) -> LLMResponse:
        del stream
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY not configured.", provider="openai")
        if not self.default_model and not model:
            raise LLMProviderError("OPENAI_MODEL_DEFAULT not configured.", provider="openai")
        if not self._breaker.allow_request():
            raise LLMProviderError(
                "OpenAI circuit breaker open.",
                provider="openai",
                status_code=503,
                is_transient=True,
                details={
                    "reset_in_seconds": self._breaker.reset_in_seconds(),
                    "last_failure": self._breaker.last_failure or self._last_error_details,
                },
            )

        model_name = (model or self.default_model).strip()
        start = time.perf_counter()
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt is not None:
                messages.append({"role": "user", "content": prompt})

        _log_llm(
            "request",
            {
                "request_id": request_id,
                "provider": "openai",
                "model": model_name,
                "prompt": _sanitize_prompt_preview(json.dumps(messages, ensure_ascii=True)),
                "input_length": len(json.dumps(messages, ensure_ascii=True)),
            },
        )

        status_info: Dict[str, Any] = {"status": "unknown", "finish_reason": "unknown"}
        usage: Dict[str, Any] = {"input": 0, "output": 0, "total": 0, "cached": None}
        payload: Dict[str, Any] = {}

        try:
            if "gpt-5" in model_name.lower():
                verbosity = verbosity or "low"
                input_items: List[Dict[str, Any]] = []
                for msg in messages:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        converted: List[Dict[str, Any]] = []
                        for part in content:
                            part_type = part.get("type")
                            if part_type in {"text", "input_text"}:
                                converted.append({"type": "input_text", "text": part.get("text", "")})
                            elif part_type in {"image_url", "input_image"}:
                                image_url = part.get("image_url")
                                if isinstance(image_url, dict):
                                    image_url = image_url.get("url")
                                converted.append({"type": "input_image", "image_url": image_url})
                        content_list = converted
                    else:
                        content_list = [{"type": "input_text", "text": str(content)}]
                    input_items.append({"role": role, "content": content_list})

                text_format = None
                json_schema_norm = _normalize_openai_schema_wrapper(json_schema) if json_schema else None
                if json_schema_norm:
                    # Use shared helper to build structured output param for Responses API
                    text_format = build_openai_structured_output(
                        db_wrapper=json_schema_norm,
                        endpoint="responses",
                        call_name=None  # Caller can provide via trace logging
                    )

                params: Dict[str, Any] = {
                    "model": model_name,
                    "input": input_items,
                    "max_output_tokens": max_tokens,
                }
                text_payload: Dict[str, Any] = {"verbosity": verbosity}
                if text_format:
                    text_payload["format"] = text_format
                params["text"] = text_payload
                reasoning_effort = (os.environ.get("OPENAI_REASONING_EFFORT") or "minimal").strip().lower()
                if reasoning_effort in {"minimal", "low", "medium", "high"}:
                    params["reasoning"] = {"effort": reasoning_effort}

                response = await self.client.responses.create(**params)
                status_info["status"] = getattr(response, "status", "completed")
                if status_info["status"] == "incomplete":
                    details = getattr(response, "incomplete_details", None)
                    reason = getattr(details, "reason", None) if details else None
                    status_info["incomplete_reason"] = reason or "unknown"

                usage_obj = getattr(response, "usage", None)
                if usage_obj is not None:
                    usage["input"] = getattr(usage_obj, "prompt_tokens", None) or getattr(usage_obj, "input_tokens", 0)
                    usage["output"] = getattr(usage_obj, "completion_tokens", None) or getattr(usage_obj, "output_tokens", 0)
                    usage["total"] = getattr(usage_obj, "total_tokens", 0)
                    prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
                    input_details = getattr(usage_obj, "input_token_details", None)
                    if prompt_details is not None:
                        usage["cached"] = getattr(prompt_details, "cached_tokens", None)
                    elif input_details is not None:
                        usage["cached"] = getattr(input_details, "cached_tokens", None)

                content = (getattr(response, "output_text", None) or "").strip()
                if not content:
                    for item in (getattr(response, "output", None) or []):
                        for block in (getattr(item, "content", None) or []):
                            text_value = getattr(block, "text", None)
                            if isinstance(text_value, str) and text_value:
                                content = text_value
                                break
                        if content:
                            break

                payload = {
                    "max_output_tokens": max_tokens,
                    "full_input": input_items,
                    "response_format_schema_name": json_schema_norm.get("name") if json_schema_norm else None,
                    "reasoning_effort": reasoning_effort,
                }
            else:
                params = {
                    "model": model_name,
                    "messages": messages,
                    "max_completion_tokens": max_tokens,
                }
                json_schema_norm = _normalize_openai_schema_wrapper(json_schema) if json_schema else None
                if json_schema_norm:
                    # Use shared helper to build structured output param for Chat Completions API
                    params["response_format"] = build_openai_structured_output(
                        db_wrapper=json_schema_norm,
                        endpoint="chat_completions",
                        call_name=None  # Caller can provide via trace logging
                    )
                if temperature is not None:
                    params["temperature"] = temperature

                response = await self.client.chat.completions.create(**params)
                status_info["status"] = "completed"
                status_info["finish_reason"] = response.choices[0].finish_reason

                usage_obj = getattr(response, "usage", None)
                if usage_obj is not None:
                    usage["input"] = getattr(usage_obj, "prompt_tokens", 0)
                    usage["output"] = getattr(usage_obj, "completion_tokens", 0)
                    usage["total"] = getattr(usage_obj, "total_tokens", 0)
                    details = getattr(usage_obj, "prompt_tokens_details", None)
                    if details is not None:
                        usage["cached"] = getattr(details, "cached_tokens", None)

                content = response.choices[0].message.content or ""
                payload = {
                    "max_output_tokens": max_tokens,
                    "full_input": messages,
                    "response_format_schema_name": json_schema_norm.get("name") if json_schema_norm else None,
                }

            self._breaker.record_success()
        except Exception as exc:
            details = self._record_failure("request_failed", exc)
            raise LLMProviderError(
                f"OpenAI request failed: {details['message']}",
                provider="openai",
                is_transient=True,
                details=details,
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        _log_llm(
            "response",
            {
                "request_id": request_id,
                "provider": "openai",
                "model": model_name,
                "latency_ms": latency_ms,
                "output_length": len(content or ""),
                "status": status_info,
            },
        )

        return LLMResponse(
            content=content or "",
            provider="openai",
            model=model_name,
            usage=usage,
            status=status_info,
            payload=payload,
            attempts=1,
            latency_ms=latency_ms,
        )

    async def generate_stream(
        self,
        *,
        messages: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str],
        prompt: Optional[str],
        json_schema: Optional[Dict[str, Any]],
        max_tokens: int,
        temperature: Optional[float],
        request_id: Optional[str],
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
    ) -> AsyncIterator[LLMStreamResponse]:
        response = await self.generate(
            messages=messages,
            system_prompt=system_prompt,
            prompt=prompt,
            json_schema=json_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            request_id=request_id,
            model=model,
            verbosity=verbosity,
        )
        yield LLMStreamResponse(
            content=response.content,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            status=response.status,
            latency_ms=response.latency_ms,
            done=True,
        )
