import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


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
        remaining = int(self.open_until - time.time())
        return max(0, remaining)


def _debug_enabled() -> bool:
    return os.environ.get("LLM_DEBUG_LOGS", "false").lower() in {"1", "true", "yes"}


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_prompt_preview(text: str, limit: int = 200) -> Dict[str, str]:
    text = text or ""
    preview = text[:limit]
    return {"preview": preview, "sha256": _hash_text(text)}


def _log_llm(event: str, payload: Dict[str, Any]) -> None:
    if not _debug_enabled():
        return
    logger = logging.getLogger("llm")
    safe_payload = {"event": event, **payload}
    logger.info(json.dumps(safe_payload))


def _normalize_messages_for_ollama(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts: List[str] = []
            for part in content:
                part_type = part.get("type")
                if part_type in {"text", "input_text"}:
                    text_parts.append(part.get("text", ""))
                elif part_type in {"image_url", "input_image"}:
                    raise LLMProviderError(
                        "Ollama does not support image inputs.",
                        provider="ollama",
                        is_transient=False,
                    )
            content = "".join(text_parts).strip()
        normalized.append({"role": role, "content": str(content)})
    return normalized


def build_ollama_chat_payload(
    model: str,
    messages: List[Dict[str, str]],
    stream: bool,
    options: Dict[str, Any],
    keep_alive: Optional[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": options,
    }
    if keep_alive:
        payload["keep_alive"] = keep_alive
    return payload


def build_ollama_generate_payload(
    model: str,
    prompt: str,
    stream: bool,
    options: Dict[str, Any],
    keep_alive: Optional[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "options": options,
    }
    if keep_alive:
        payload["keep_alive"] = keep_alive
    return payload


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

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            kwargs["timeout"] = self.timeout_seconds
            self._client = AsyncOpenAI(**kwargs)
        return self._client

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
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY not configured.", provider="openai")

        model_name = model or self.default_model
        start = time.perf_counter()

        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt is not None:
                messages.append({"role": "user", "content": prompt})

        prompt_text = json.dumps(messages, ensure_ascii=True)
        _log_llm(
            "request",
            {
                "request_id": request_id,
                "provider": "openai",
                "model": model_name,
                "prompt": _sanitize_prompt_preview(prompt_text),
                "input_length": len(prompt_text),
            },
        )

        status_info: Dict[str, Any] = {"status": "unknown", "finish_reason": "unknown"}
        usage: Dict[str, Any] = {"input": 0, "output": 0, "total": 0, "cached": None}
        payload: Dict[str, Any] = {}

        if "gpt-5" in model_name.lower():
            verbosity = verbosity or "low"

            input_items: List[Dict[str, Any]] = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if isinstance(content, list):
                    converted = []
                    for part in content:
                        part_type = part.get("type")
                        if part_type == "text":
                            converted.append({"type": "input_text", "text": part.get("text", "")})
                        elif part_type == "image_url":
                            converted.append({"type": "input_image", "image_url": part.get("image_url", {}).get("url")})
                    content_list = converted
                else:
                    content_list = [{"type": "input_text", "text": str(content)}]
                input_items.append({"role": role, "content": content_list})

            text_format = None
            if json_schema:
                text_format = {
                    "type": "json_schema",
                    "name": json_schema.get("name", "schema"),
                    "schema": json_schema.get("schema", json_schema),
                    "strict": json_schema.get("strict", True),
                }

            params: Dict[str, Any] = {
                "model": model_name,
                "input": input_items,
                "max_output_tokens": max_tokens,
            }
            if text_format:
                params["text"] = {"verbosity": verbosity, "format": text_format}
            response = await self.client.responses.create(**params)

            if hasattr(response, "status"):
                status_info["status"] = response.status
                if response.status == "incomplete":
                    details = getattr(response, "incomplete_details", None) or {}
                    status_info["incomplete_reason"] = details.get("reason", "unknown")

            if hasattr(response, "usage"):
                if hasattr(response.usage, "prompt_tokens"):
                    usage["input"] = response.usage.prompt_tokens
                    usage["output"] = response.usage.completion_tokens
                    usage["total"] = response.usage.total_tokens
                elif hasattr(response.usage, "input_tokens"):
                    usage["input"] = response.usage.input_tokens
                    usage["output"] = response.usage.output_tokens
                    usage["total"] = response.usage.total_tokens
                if hasattr(response.usage, "prompt_tokens_details"):
                    usage["cached"] = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
                elif hasattr(response.usage, "input_token_details"):
                    usage["cached"] = getattr(response.usage.input_token_details, "cached_tokens", 0)

            content = ""
            if hasattr(response, "output") and response.output:
                for item in response.output:
                    if hasattr(item, "content") and item.content:
                        content = item.content[0].text
                        break

            payload = {
                "max_output_tokens": max_tokens,
                "full_input": input_items,
                "response_format_schema_name": json_schema.get("name") if json_schema else None,
            }
        else:
            params: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "max_completion_tokens": max_tokens,
            }
            if json_schema:
                params["response_format"] = {"type": "json_schema", "json_schema": json_schema}
            if temperature is not None and "gpt-5" not in model_name.lower():
                params["temperature"] = temperature

            response = await self.client.chat.completions.create(**params)
            status_info["status"] = "completed"
            status_info["finish_reason"] = response.choices[0].finish_reason

            if hasattr(response, "usage"):
                usage["input"] = response.usage.prompt_tokens
                usage["output"] = response.usage.completion_tokens
                usage["total"] = response.usage.total_tokens
                if hasattr(response.usage, "prompt_tokens_details") and response.usage.prompt_tokens_details:
                    usage["cached"] = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
                if usage["cached"] is None and hasattr(response.usage, "cached_tokens"):
                    usage["cached"] = response.usage.cached_tokens

            content = response.choices[0].message.content or ""
            payload = {
                "max_output_tokens": max_tokens,
                "full_input": messages,
                "response_format_schema_name": json_schema.get("name") if json_schema else None,
            }

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


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int,
        max_retries: int,
        keep_alive: Optional[str],
        temperature: float,
        top_p: float,
        context_tokens: Optional[int],
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.keep_alive = keep_alive
        self.temperature = temperature
        self.top_p = top_p
        self.context_tokens = context_tokens
        self._breaker = CircuitBreaker()
        self._last_error_details: Optional[Dict[str, Any]] = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    @staticmethod
    def _stringify_exception(exc: Exception) -> str:
        message = str(exc).strip()
        if message:
            return message
        return repr(exc)

    def _build_error_details(self, category: str, exc: Exception, status_code: Optional[int] = None) -> Dict[str, Any]:
        details: Dict[str, Any] = {
            "category": category,
            "exception_class": exc.__class__.__name__,
            "message": self._stringify_exception(exc),
            "base_url": self.base_url,
        }
        if status_code is not None:
            details["status_code"] = status_code
        return details

    def _record_transient_failure(self, details: Dict[str, Any]) -> None:
        self._last_error_details = details
        self._breaker.record_failure(details)

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

    def _build_options(self, max_tokens: int, temperature: Optional[float]) -> Dict[str, Any]:
        temp = self.temperature if temperature is None else temperature
        options: Dict[str, Any] = {
            "temperature": temp,
            "top_p": self.top_p,
            "num_predict": max_tokens,
        }
        if self.context_tokens:
            options["num_ctx"] = self.context_tokens
        return options

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
        if not self._breaker.allow_request():
            reset_in_seconds = self._breaker.reset_in_seconds()
            failure_details = self._breaker.last_failure or self._last_error_details or {
                "base_url": self.base_url,
            }
            raise LLMProviderError(
                "Ollama circuit breaker open.",
                provider="ollama",
                status_code=503,
                is_transient=True,
                details={
                    "base_url": self.base_url,
                    "reset_in_seconds": reset_in_seconds,
                    "last_failure": failure_details,
                },
            )

        model_name = model or self.model
        start = time.perf_counter()
        attempts = 0
        last_error: Optional[Exception] = None

        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt is not None:
                messages.append({"role": "user", "content": prompt})

        use_chat = len(messages) > 0
        normalized_messages = _normalize_messages_for_ollama(messages) if use_chat else []
        prompt_text = json.dumps(normalized_messages, ensure_ascii=True) if use_chat else (prompt or "")
        _log_llm(
            "request",
            {
                "request_id": request_id,
                "provider": "ollama",
                "model": model_name,
                "prompt": _sanitize_prompt_preview(prompt_text),
                "input_length": len(prompt_text),
            },
        )

        options = self._build_options(max_tokens, temperature)
        if use_chat:
            endpoint = "/api/chat"
            payload = build_ollama_chat_payload(
                model=model_name,
                messages=normalized_messages,
                stream=stream,
                options=options,
                keep_alive=self.keep_alive,
            )
        else:
            endpoint = "/api/generate"
            payload = build_ollama_generate_payload(
                model=model_name,
                prompt=prompt or "",
                stream=stream,
                options=options,
                keep_alive=self.keep_alive,
            )

        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            try:
                response = await self._client.post(endpoint, json=payload)
                if response.status_code >= 500:
                    details = self._build_error_details(
                        "http_5xx",
                        Exception(f"Ollama server error {response.status_code}"),
                        status_code=response.status_code,
                    )
                    raise LLMProviderError(
                        f"Ollama server error: {response.status_code}",
                        provider="ollama",
                        status_code=response.status_code,
                        is_transient=True,
                        details=details,
                    )
                if response.status_code >= 400:
                    details = self._build_error_details(
                        "http_4xx",
                        Exception(f"Ollama client error {response.status_code}"),
                        status_code=response.status_code,
                    )
                    raise LLMProviderError(
                        f"Ollama client error: {response.status_code}",
                        provider="ollama",
                        status_code=response.status_code,
                        is_transient=False,
                        details=details,
                    )

                content = ""
                if stream:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("done"):
                            break
                        delta = data.get("message", {}).get("content") or data.get("response", "")
                        if delta:
                            content += delta
                else:
                    try:
                        data = response.json()
                    except ValueError as e:
                        raise LLMProviderError(
                            "Invalid JSON response from Ollama.",
                            provider="ollama",
                            status_code=502,
                            is_transient=False,
                            details=self._build_error_details("invalid_json", e),
                        ) from e
                    content = data.get("message", {}).get("content")
                    if content is None:
                        content = data.get("response")

                if not isinstance(content, str) or not content.strip():
                    raise LLMProviderError(
                        "Empty response from Ollama.",
                        provider="ollama",
                        is_transient=False,
                        details={
                            "base_url": self.base_url,
                            "category": "empty_response",
                        },
                    )

                self._breaker.record_success()
                latency_ms = int((time.perf_counter() - start) * 1000)
                usage = {"input": 0, "output": 0, "total": 0, "cached": None}
                status_info = {"status": "completed", "finish_reason": "stop"}
                payload_summary = {
                    "max_output_tokens": max_tokens,
                    "response_format_schema_name": json_schema.get("name") if json_schema else None,
                }

                _log_llm(
                    "response",
                    {
                        "request_id": request_id,
                        "provider": "ollama",
                        "model": model_name,
                        "latency_ms": latency_ms,
                        "output_length": len(content),
                    },
                )

                return LLMResponse(
                    content=content,
                    provider="ollama",
                    model=model_name,
                    usage=usage,
                    status=status_info,
                    payload=payload_summary,
                    attempts=attempts,
                    latency_ms=latency_ms,
                )
            except LLMProviderError as e:
                last_error = e
                if not e.is_transient:
                    raise
                if attempt >= self.max_retries:
                    self._record_transient_failure(
                        e.details
                        or {
                            "base_url": self.base_url,
                            "exception_class": e.__class__.__name__,
                            "message": str(e),
                        }
                    )
                    raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                if attempt >= self.max_retries:
                    if isinstance(e, httpx.ConnectTimeout):
                        category = "connect_timeout"
                    elif isinstance(e, httpx.ReadTimeout):
                        category = "read_timeout"
                    elif isinstance(e, httpx.TimeoutException):
                        category = "timeout"
                    else:
                        category = "connection_error"
                    details = self._build_error_details(category, e)
                    self._record_transient_failure(details)
                    raise LLMProviderError(
                        f"Ollama connection error: {self._stringify_exception(e)}",
                        provider="ollama",
                        is_transient=True,
                        details=details,
                    ) from e
            except httpx.HTTPError as e:
                last_error = e
                if attempt >= self.max_retries:
                    details = self._build_error_details("http_error", e)
                    raise LLMProviderError(
                        f"Ollama HTTP error: {self._stringify_exception(e)}",
                        provider="ollama",
                        is_transient=False,
                        details=details,
                    ) from e
            await asyncio.sleep(min(2 ** attempt, 4))

        raise LLMProviderError(
            f"Ollama request failed: {last_error}",
            provider="ollama",
            is_transient=True,
        )
