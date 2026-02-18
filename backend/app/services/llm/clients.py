import hashlib
import json
import logging
import os
import time
import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import httpx

from app.utils.structured_output_builder import build_openai_structured_output, log_openai_request_trace
from app.utils.schema_wrapper_validator import validate_schema_wrapper, SchemaWrapperCorruptError


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

    STRICT BEHAVIOR (NO FALLBACK):
    - If a half-wrapper {"schema": {...}} is received, RAISE immediately.
    - If wrapper is missing required keys, RAISE immediately.
    - We do NOT silently fallback to raw_schema anymore - that hides upstream bugs.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SchemaWrapperCorruptError(
            f"json_schema must be a dict, got {type(raw).__name__}",
            wrapper_keys=None,
        )

    keys = set(raw.keys())

    # Canonical DB wrapper - validate and return
    if {"type", "name", "strict", "schema"}.issubset(keys) and raw.get("type") == "json_schema":
        # Validate strictly (will raise if corrupt)
        validate_schema_wrapper(raw, context="normalize_wrapper")
        return raw

    # OpenAI chat-completions wrapper variant: {"type":"json_schema","json_schema":{name,strict,schema}}
    if raw.get("type") == "json_schema" and isinstance(raw.get("json_schema"), dict):
        inner = raw["json_schema"]
        if not inner.get("name") or not isinstance(inner.get("name"), str):
            raise SchemaWrapperCorruptError(
                f"json_schema.name must be non-empty string, got {inner.get('name')!r}",
                wrapper_keys=list(inner.keys()),
            )
        result = {
            "type": "json_schema",
            "name": inner.get("name"),
            "strict": bool(inner.get("strict", True)),
            "schema": inner.get("schema", {}),
        }
        validate_schema_wrapper(result, context="normalize_wrapper (chat variant)")
        return result

    # Legacy/partial wrapper variant: {"name": "...", "schema": {...}, "strict": true}
    if "type" not in keys and {"name", "schema"}.issubset(keys):
        if not raw.get("name") or not isinstance(raw.get("name"), str):
            raise SchemaWrapperCorruptError(
                f"json_schema.name must be non-empty string, got {raw.get('name')!r}",
                wrapper_keys=list(keys),
            )
        result = {
            "type": "json_schema",
            "name": raw.get("name"),
            "strict": bool(raw.get("strict", True)),
            "schema": raw.get("schema", {}),
        }
        validate_schema_wrapper(result, context="normalize_wrapper (legacy variant)")
        return result

    # FATAL: Half-wrapper detected: {"schema": {...}} (THIS IS A BUG UPSTREAM)
    if keys == {"schema"} and isinstance(raw.get("schema"), dict):
        raise SchemaWrapperCorruptError(
            "Half-wrapper schema detected (only 'schema' key). "
            "Upstream logic broken. Aborting to prevent silent fallback.",
            wrapper_keys=list(keys),
        )

    # FATAL: Raw Draft schema without proper wrapper
    # Previously we would silently wrap as raw_schema - now we fail fast
    if "$schema" in raw or raw.get("type") in {"object", "array", "string", "number", "integer", "boolean", "null"} or "properties" in raw:
        raise SchemaWrapperCorruptError(
            "Raw JSON Schema received without proper wrapper. "
            "DB schemas must always be wrapped with {type, name, strict, schema}.",
            wrapper_keys=list(keys)[:10],
        )

    # Unknown shape: fail loudly
    raise SchemaWrapperCorruptError(
        f"Unknown json_schema format. Keys={sorted(keys)[:10]}",
        wrapper_keys=list(keys)[:10],
    )




class OpenAIClient:
    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout_seconds: int,
        default_model: str,
        allow_non_gpt5_model: bool = False,
        allow_missing_api_key: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.default_model = default_model
        self.allow_non_gpt5_model = bool(allow_non_gpt5_model)
        self.allow_missing_api_key = bool(allow_missing_api_key)
        self._client = None
        self._breaker = CircuitBreaker(
            failure_threshold=int((os.environ.get("OPENAI_BREAKER_FAILURE_THRESHOLD") or "3").strip()),
            reset_seconds=int((os.environ.get("OPENAI_BREAKER_RESET_SECONDS") or "30").strip()),
        )
        self._last_error_details: Optional[Dict[str, Any]] = None
        self._required_model = "gpt-5-mini"

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            effective_api_key = self.api_key or ("sk-local" if self.allow_missing_api_key else None)
            kwargs: Dict[str, Any] = {"api_key": effective_api_key, "timeout": self.timeout_seconds}
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
        max_tokens: Optional[int],
        temperature: Optional[float],
        top_p: Optional[float] = None,
        stream: bool = False,
        request_id: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResponse:
        del stream
        if not self.api_key and not self.allow_missing_api_key:
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
        if not self.allow_non_gpt5_model and model_name != self._required_model:
            raise LLMProviderError(
                f"Model override rejected. Expected {self._required_model}, got {model_name}.",
                provider="openai",
            )
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
                if json_schema and reasoning_effort not in {"minimal", "low", "medium", "high"}:
                    reasoning_effort = "minimal"
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
                }
                if max_tokens is not None:
                    params["max_output_tokens"] = max_tokens
                text_payload: Dict[str, Any] = {"verbosity": verbosity}
                if text_format:
                    text_payload["format"] = text_format
                params["text"] = text_payload
                if top_p is not None:
                    params["top_p"] = top_p
                if reasoning_effort in {"minimal", "low", "medium", "high"}:
                    params["reasoning"] = {"effort": reasoning_effort}

                effective_client = self.client.with_options(timeout=(max(1.0, float(timeout_ms) / 1000.0))) if timeout_ms else self.client
                response = await effective_client.responses.create(**params)
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
                }
                if max_tokens is not None:
                    params["max_completion_tokens"] = max_tokens
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
                if top_p is not None:
                    params["top_p"] = top_p

                effective_client = self.client.with_options(timeout=(max(1.0, float(timeout_ms) / 1000.0))) if timeout_ms else self.client
                response = await effective_client.chat.completions.create(**params)
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
        max_tokens: Optional[int],
        temperature: Optional[float],
        top_p: Optional[float] = None,
        request_id: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncIterator[LLMStreamResponse]:
        response = await self.generate(
            messages=messages,
            system_prompt=system_prompt,
            prompt=prompt,
            json_schema=json_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=False,
            request_id=request_id,
            timeout_ms=timeout_ms,
            model=model,
            verbosity=verbosity,
            reasoning_effort=reasoning_effort,
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


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        default_model: str,
        timeout_seconds: int,
        connect_timeout_seconds: int,
        default_temperature: Optional[float] = 0.2,
        default_num_ctx: Optional[int] = 4096,
        default_max_tokens: Optional[int] = None,
        http_client_factory: Optional[Any] = None,
    ):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.default_model = (default_model or "").strip()
        self.timeout_seconds = max(1, int(timeout_seconds or 60))
        self.connect_timeout_seconds = max(1, int(connect_timeout_seconds or 5))
        self.default_temperature = default_temperature
        self.default_num_ctx = default_num_ctx
        self.default_max_tokens = default_max_tokens
        self._http_client_factory = http_client_factory
        self.connect_retries = max(0, int((os.environ.get("OLLAMA_CONNECT_RETRIES") or "2").strip()))
        self.retry_backoff_ms = max(0, int((os.environ.get("OLLAMA_RETRY_BACKOFF_MS") or "250").strip()))

    def _candidate_base_urls(self) -> List[str]:
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        candidates: List[str] = [self.base_url]

        def _with_host(new_host: str) -> str:
            netloc = new_host
            if parsed.port:
                netloc = f"{new_host}:{parsed.port}"
            return urlunparse((parsed.scheme or "http", netloc, parsed.path, "", "", "")).rstrip("/")

        if host == "host.docker.internal":
            candidates.append(_with_host("localhost"))
            candidates.append(_with_host("127.0.0.1"))
        elif host in {"localhost", "127.0.0.1"}:
            candidates.append(_with_host("host.docker.internal"))

        seen: set[str] = set()
        uniq: List[str] = []
        for c in candidates:
            if c not in seen:
                uniq.append(c)
                seen.add(c)
        return uniq

    def _build_prompt(
        self,
        *,
        messages: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str],
        prompt: Optional[str],
        json_schema: Optional[Dict[str, Any]],
    ) -> str:
        if prompt:
            prompt_text = str(prompt)
        else:
            chunks: List[str] = []
            for msg in messages or []:
                role = str(msg.get("role") or "user").upper()
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts: List[str] = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in {"text", "input_text"}:
                            text_parts.append(str(part.get("text") or ""))
                    content_text = "\n".join([p for p in text_parts if p])
                else:
                    content_text = str(content)
                chunks.append(f"[{role}]\n{content_text}")
            prompt_text = "\n\n".join([c for c in chunks if c.strip()])

        if json_schema:
            schema_payload = json.dumps(json_schema, ensure_ascii=True)
            prompt_text = (
                f"{prompt_text}\n\n"
                "Return ONLY valid JSON that matches this schema exactly:\n"
                f"{schema_payload}"
            )
        return prompt_text.strip()

    @staticmethod
    def _extract_ollama_format_schema(json_schema: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(json_schema, dict):
            return None
        # Support internal wrapper form: {"type":"json_schema", "schema": {...}}
        if json_schema.get("type") == "json_schema" and isinstance(json_schema.get("schema"), dict):
            return json_schema.get("schema")
        # Support direct JSON schema body.
        if isinstance(json_schema.get("properties"), dict) or json_schema.get("type") in {
            "object",
            "array",
            "string",
            "number",
            "integer",
            "boolean",
            "null",
        }:
            return json_schema
        return None

    @staticmethod
    def _should_enforce_english(model_name: str) -> bool:
        return str(model_name or "").strip().lower() == "qwen2.5-math-7b-instruct-q4_k_m:latest"

    async def generate(
        self,
        *,
        messages: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str],
        prompt: Optional[str],
        json_schema: Optional[Dict[str, Any]],
        max_tokens: Optional[int],
        temperature: Optional[float],
        top_p: Optional[float] = None,
        stream: bool = False,
        request_id: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResponse:
        del stream, top_p, verbosity, reasoning_effort

        model_name = (model or self.default_model).strip()
        if not model_name:
            raise LLMProviderError("OLLAMA_MODEL not configured.", provider="ollama")

        use_format_schema = (os.environ.get("OLLAMA_USE_FORMAT_SCHEMA") or "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        include_schema_in_prompt = (
            os.environ.get("OLLAMA_INCLUDE_SCHEMA_IN_PROMPT") or "false"
        ).strip().lower() in {"1", "true", "yes"}
        prompt_schema = json_schema if include_schema_in_prompt else None

        prompt_text = self._build_prompt(
            messages=messages,
            system_prompt=None,
            prompt=prompt,
            json_schema=prompt_schema,
        )
        system_text = (system_prompt or "").strip()
        english_only_enforced = self._should_enforce_english(model_name)
        if english_only_enforced:
            system_text = (
                "You must answer in English only. Do not use any other language.\n\n"
                f"{system_text}"
            ).strip()
        if not prompt_text:
            raise LLMProviderError("Ollama prompt is empty.", provider="ollama")

        options: Dict[str, Any] = {}
        effective_temp = self.default_temperature if temperature is None else temperature
        if effective_temp is not None:
            options["temperature"] = float(effective_temp)
        if self.default_num_ctx:
            options["num_ctx"] = int(self.default_num_ctx)
        effective_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens
        if effective_max_tokens is not None:
            options["num_predict"] = int(effective_max_tokens)

        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt_text,
            "stream": False,
        }
        if system_text:
            payload["system"] = system_text
        format_schema = self._extract_ollama_format_schema(json_schema) if use_format_schema else None
        if format_schema is not None:
            payload["format"] = format_schema
        if options:
            payload["options"] = options

        timeout = httpx.Timeout(
            timeout=max(1.0, float(timeout_ms) / 1000.0) if timeout_ms else float(self.timeout_seconds),
            connect=float(self.connect_timeout_seconds),
        )

        start = time.perf_counter()
        _log_llm(
            "request",
            {
                "request_id": request_id,
                "provider": "ollama",
                "model": model_name,
                "base_url": self.base_url,
                "prompt": _sanitize_prompt_preview(prompt_text),
                "input_length": len(prompt_text),
            },
        )

        async def _post_with_retries(request_payload: Dict[str, Any]) -> httpx.Response:
            resp_local: Optional[httpx.Response] = None
            last_connect_exc_local: Optional[Exception] = None
            last_timeout_exc_local: Optional[Exception] = None
            candidates_local = self._candidate_base_urls()
            tries_per_base_local = self.connect_retries + 1

            for candidate_base in candidates_local:
                for attempt_no in range(1, tries_per_base_local + 1):
                    try:
                        if self._http_client_factory:
                            client_ctx = self._http_client_factory(timeout=timeout)
                        else:
                            client_ctx = httpx.AsyncClient(timeout=timeout)

                        async with client_ctx as client:
                            resp_local = await client.post(f"{candidate_base}/api/generate", json=request_payload)

                        if candidate_base != self.base_url:
                            self.base_url = candidate_base
                        break
                    except httpx.ConnectError as exc:
                        last_connect_exc_local = exc
                        if attempt_no < tries_per_base_local:
                            await asyncio.sleep(self.retry_backoff_ms / 1000.0)
                    except httpx.TimeoutException as exc:
                        last_timeout_exc_local = exc
                        if attempt_no < tries_per_base_local:
                            await asyncio.sleep(self.retry_backoff_ms / 1000.0)
                if resp_local is not None:
                    break

            if resp_local is None:
                if last_connect_exc_local is not None:
                    raise last_connect_exc_local
                if last_timeout_exc_local is not None:
                    raise last_timeout_exc_local
                raise RuntimeError("No HTTP response from Ollama.")
            return resp_local

        try:
            resp = await _post_with_retries(payload)
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                "Ollama base URL unreachable.",
                provider="ollama",
                status_code=503,
                is_transient=True,
                details={
                    "base_url": self.base_url,
                    "candidate_base_urls": self._candidate_base_urls(),
                    "connect_retries": self.connect_retries,
                    "error": str(exc),
                },
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                "Ollama request timed out.",
                provider="ollama",
                status_code=504,
                is_transient=True,
                details={
                    "base_url": self.base_url,
                    "candidate_base_urls": self._candidate_base_urls(),
                    "connect_retries": self.connect_retries,
                    "timeout_seconds": self.timeout_seconds,
                    "error": str(exc),
                },
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama request failed: {str(exc).strip() or repr(exc)}",
                provider="ollama",
                status_code=503,
                is_transient=True,
                details={"base_url": self.base_url},
            ) from exc

        if resp.status_code >= 500 and format_schema is not None:
            body_preview = (resp.text or "")[:500].lower()
            if "model runner has unexpectedly stopped" in body_preview:
                safe_payload = dict(payload)
                safe_payload.pop("format", None)
                safe_options = dict(options)
                try:
                    safe_num_ctx = int((os.environ.get("OLLAMA_SAFE_NUM_CTX") or "2048").strip())
                except Exception:
                    safe_num_ctx = 2048
                if safe_num_ctx > 0:
                    current_ctx = int(safe_options.get("num_ctx") or safe_num_ctx)
                    safe_options["num_ctx"] = min(current_ctx, safe_num_ctx)
                try:
                    safe_num_predict = int((os.environ.get("OLLAMA_SAFE_NUM_PREDICT") or "1800").strip())
                except Exception:
                    safe_num_predict = 1800
                if safe_num_predict > 0:
                    current_predict = safe_options.get("num_predict")
                    if current_predict is None:
                        safe_options["num_predict"] = safe_num_predict
                    else:
                        safe_options["num_predict"] = min(int(current_predict), safe_num_predict)
                if safe_options:
                    safe_payload["options"] = safe_options
                try:
                    fallback_resp = await _post_with_retries(safe_payload)
                    if fallback_resp.status_code < 400:
                        resp = fallback_resp
                        payload = safe_payload
                        options = safe_options
                except Exception:
                    pass

        if resp.status_code >= 400:
            body_preview = (resp.text or "")[:300]
            details = {"base_url": self.base_url, "status_code": resp.status_code, "body": body_preview}
            if resp.status_code == 404:
                message = f"Ollama model '{model_name}' not found."
            else:
                message = f"Ollama HTTP error status={resp.status_code}."
            raise LLMProviderError(
                message,
                provider="ollama",
                status_code=resp.status_code,
                is_transient=resp.status_code >= 500,
                details=details,
            )

        try:
            data = resp.json()
        except Exception as exc:
            raise LLMProviderError(
                "Ollama returned non-JSON response.",
                provider="ollama",
                status_code=502,
                details={"base_url": self.base_url, "body_preview": (resp.text or "")[:300]},
            ) from exc

        content = str(data.get("response") or "").strip()
        if not content:
            raise LLMProviderError(
                "Ollama returned empty response text.",
                provider="ollama",
                status_code=502,
                details={"base_url": self.base_url, "payload_keys": sorted(list(data.keys()))[:20]},
            )

        usage = {
            "input": int(data.get("prompt_eval_count") or 0),
            "output": int(data.get("eval_count") or 0),
            "total": int((data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)),
            "cached": None,
            "prompt_eval_duration": data.get("prompt_eval_duration"),
            "eval_duration": data.get("eval_duration"),
            "total_duration": data.get("total_duration"),
            "load_duration": data.get("load_duration"),
        }
        status = {
            "status": "completed",
            "finish_reason": data.get("done_reason") or ("stop" if data.get("done") else "unknown"),
            "done": bool(data.get("done")),
        }

        latency_ms = int((time.perf_counter() - start) * 1000)
        _log_llm(
            "response",
            {
                "request_id": request_id,
                "provider": "ollama",
                "model": model_name,
                "latency_ms": latency_ms,
                "output_length": len(content),
                "status": status,
            },
        )

        return LLMResponse(
            content=content,
            provider="ollama",
            model=model_name,
            usage=usage,
            status=status,
            payload={
                "base_url": self.base_url,
                "full_input_prompt": prompt_text,
                "ollama_metrics": {
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "prompt_eval_duration": data.get("prompt_eval_duration"),
                    "eval_count": data.get("eval_count"),
                    "eval_duration": data.get("eval_duration"),
                },
                "options": options,
                "english_only_enforced": english_only_enforced,
            },
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
        max_tokens: Optional[int],
        temperature: Optional[float],
        top_p: Optional[float] = None,
        request_id: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        model: Optional[str] = None,
        verbosity: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncIterator[LLMStreamResponse]:
        response = await self.generate(
            messages=messages,
            system_prompt=system_prompt,
            prompt=prompt,
            json_schema=json_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=False,
            request_id=request_id,
            timeout_ms=timeout_ms,
            model=model,
            verbosity=verbosity,
            reasoning_effort=reasoning_effort,
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

