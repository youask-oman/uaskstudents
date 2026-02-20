# Runtime Safety Report

Generated: 2026-02-20T04:48:44.509Z

## Scope
- Static audit only (code + compose). No runtime fault-injection harness in this report.

## Timeouts
- docker-compose.yml:26:      OLLAMA_TIMEOUT_SECONDS: "180"
- docker-compose.yml:27:      OLLAMA_CONNECT_TIMEOUT_SECONDS: "25"
- docker-compose.yml:33:      DB_POOL_TIMEOUT_SECONDS: "8"
- docker-compose.yml:36:      API_CONCURRENCY_ACQUIRE_TIMEOUT_MS: "150"
- docker-compose.yml:51:      timeout: 3s
- docker-compose.yml:95:      OLLAMA_TIMEOUT_SECONDS: "180"
- docker-compose.yml:96:      OLLAMA_CONNECT_TIMEOUT_SECONDS: "25"
- docker-compose.yml:149:      OLLAMA_TIMEOUT_SECONDS: "180"
- docker-compose.yml:150:      OLLAMA_CONNECT_TIMEOUT_SECONDS: "25"
- docker-compose.yml:204:      timeout: 3s
- docker-compose.yml:218:      timeout: 3s
- backend/app\api_admin_credits.py:106:    timeout_ms: Optional[int] = None
- backend/app\api_admin_credits.py:651:                "timeout_ms": _val(r, "timeout_ms"),
- backend/app\api_admin_credits.py:705:        "timeout_ms": getattr(binding, "timeout_ms", None),
- backend/app\api_admin.py:579:                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
- backend/app\api_admin.py:1093:        inspector = celery_app.control.inspect(timeout=1.0)
- backend/app\api.py:3078:                    timeout=float(os.environ.get("OPENAI_OCR_TIMEOUT_SECONDS", "60")),
- backend/app\api.py:11928:                timeout=2
- backend/app\api.py:14992:    timeout_ms: Optional[int] = None
- backend/app\api.py:15074:    timeout_ms: Optional[int] = None

## Retries And Backoff
- docker-compose.yml:52:      retries: 10
- docker-compose.yml:205:      retries: 20
- docker-compose.yml:219:      retries: 20
- backend/app\api_stripe.py:84:            # Failed process_status will be visible in Admin Dashboard for retry.
- backend/app\api_stripe.py:94:        # Always return 200-ish to Stripe unless it's a retryable system failure
- backend/app\api_admin_credits.py:111:    json_retry_max_output_tokens: Optional[int] = None
- backend/app\api_admin_credits.py:112:    json_retry_max_attempts: Optional[int] = None
- backend/app\api_admin_credits.py:120:    retry_cap_tokens: Optional[int] = None
- backend/app\api_admin_credits.py:656:                "json_retry_max_output_tokens": _val(r, "json_retry_max_output_tokens"),
- backend/app\api_admin_credits.py:657:                "json_retry_max_attempts": _val(r, "json_retry_max_attempts"),
- backend/app\api_admin_credits.py:665:                "retry_cap_tokens": _val(r, "retry_cap_tokens"),
- backend/app\api.py:3675:            retry_crop = ImageEnhance.Contrast(upscaled).enhance(1.4)
- backend/app\api.py:3676:            retry_crop = retry_crop.filter(ImageFilter.SHARPEN)
- backend/app\api.py:3677:            retry_metrics = _crop_quality_metrics(retry_crop)
- backend/app\api.py:3679:                "extract_questions retry metrics: size=%sx%s stddev=%.2f white=%.3f",
- backend/app\api.py:3680:                int(retry_metrics["width"]),
- backend/app\api.py:3681:                int(retry_metrics["height"]),
- backend/app\api.py:3682:                retry_metrics["stddev"],
- backend/app\api.py:3683:                retry_metrics["white_pct"]
- backend/app\api.py:3685:            if not _is_low_text_crop(retry_metrics):

## Circuit Breaker
- backend/app/services/llm/clients.py:56:class CircuitBreaker:
- backend/app/services/llm/clients.py:219:        self._breaker = CircuitBreaker(
- backend/app/services/llm/clients.py:238:    def get_circuit_breaker_state(self) -> Dict[str, Any]:
- backend/app/services/llm/clients.py:240:            "failure_count": self._breaker.failure_count,
- backend/app/services/llm/clients.py:241:            "open": not self._breaker.allow_request(),
- backend/app/services/llm/clients.py:242:            "reset_in_seconds": self._breaker.reset_in_seconds(),
- backend/app/services/llm/clients.py:243:            "last_failure": self._breaker.last_failure or self._last_error_details,
- backend/app/services/llm/clients.py:246:    def reset_circuit_breaker(self) -> None:
- backend/app/services/llm/clients.py:247:        self._breaker.reset()
- backend/app/services/llm/clients.py:259:        self._breaker.record_failure(details)
- backend/app/services/llm/clients.py:284:        if not self._breaker.allow_request():
- backend/app/services/llm/clients.py:286:                "OpenAI circuit breaker open.",
- backend/app/services/llm/clients.py:291:                    "reset_in_seconds": self._breaker.reset_in_seconds(),
- backend/app/services/llm/clients.py:292:                    "last_failure": self._breaker.last_failure or self._last_error_details,
- backend/app/services/llm/clients.py:453:            self._breaker.record_success()
- backend/app/services\llm\clients.py:56:class CircuitBreaker:
- backend/app/services\llm\clients.py:219:        self._breaker = CircuitBreaker(
- backend/app/services\llm\clients.py:238:    def get_circuit_breaker_state(self) -> Dict[str, Any]:
- backend/app/services\llm\clients.py:240:            "failure_count": self._breaker.failure_count,
- backend/app/services\llm\clients.py:241:            "open": not self._breaker.allow_request(),

## Backpressure And Concurrency Controls
- docker-compose.yml:125:    command: celery -A app.worker.celery_app worker --loglevel=info --concurrency=${WORKER_CONCURRENCY:-4}
- docker-compose.yml:174:    command: celery -A app.worker.celery_app worker --loglevel=info --concurrency=${WHATSAPP_WORKER_CONCURRENCY:-2} -Q whatsapp
- backend/app/worker.py:6:from celery import Celery
- backend/app/worker.py:62:celery_app = Celery(
- backend/app/worker.py:68:celery_app.conf.update(
- backend/app/worker.py:74:    task_default_queue="celery",
- backend/app/worker.py:75:    task_queues=(
- backend/app/worker.py:76:        Queue("celery"),
- backend/app/worker.py:80:        "whatsapp_ocr_extract": {"queue": "whatsapp"},
- backend/app/worker.py:81:        "whatsapp_solve": {"queue": "whatsapp"},
- backend/app/worker.py:85:            "rate_limit": os.environ.get("WHATSAPP_OCR_RATE_LIMIT", "20/m"),
- backend/app/worker.py:88:            "rate_limit": os.environ.get("WHATSAPP_SOLVE_RATE_LIMIT", "30/m"),
- backend/app/worker.py:100:celery_app.conf.beat_schedule = {
- backend/app/worker.py:123:@celery_app.task(
- backend/app/worker.py:325:@celery_app.task(
- backend/app/api.py:94:from app.worker import celery_app
- backend/app/api.py:118:from slowapi import Limiter, _rate_limit_exceeded_handler
- backend/app/api.py:176:def _enqueue_attempt_graph_render(attempt_id: Optional[str]) -> None:
- backend/app/api.py:180:        celery_app.send_task("render_attempt_graph", args=[attempt_id], queue="celery")
- backend/app/api.py:182:        logger.warning("graph_enqueue_failed attempt_id=%s reason=%s", attempt_id, str(exc))

## Idempotency And Duplicate Work Protection
- backend/app/api.py:1177:    idempotency_key: Optional[str] = Field(
- backend/app/api.py:2750:    idempotency_key: Optional[str] = None
- backend/app/api.py:3965:            idempotency_key=hold_request_id,
- backend/app/api.py:4170:            idempotency_key=body.idempotency_key,
- backend/app/api.py:4271:                idempotency_key=reserve_result.idempotency_key,
- backend/app/api.py:5773:    # Generate unique Request ID (idempotent when idempotency_key is provided)
- backend/app/api.py:5774:    request_id = (body.idempotency_key or "").strip() or str(uuid.uuid4())
- backend/app/api.py:5913:                idempotency_key=body.idempotency_key,
- backend/app/api.py:6939:    # 0. Phase 1 Hardening: Distinct IDs (idempotent when idempotency_key is provided)
- backend/app/api.py:6940:    request_id = (body.idempotency_key or "").strip() or str(uuid.uuid4())
- backend/app/api.py:7266:                    idempotency_key=getattr(body, "idempotency_key", None),
- backend/app/api.py:7323:                        idempotency_key=reserve_result.idempotency_key,
- backend/app/api.py:7551:    if body.idempotency_key:
- backend/app/api.py:7762:                idempotency_key=body.idempotency_key,
- backend/app/models\__init__.py:348:    idempotency_key: Optional[str] = Field(default=None, index=True)
- backend/app/models\__init__.py:1198:    idempotency_key: Optional[str] = Field(default=None, unique=True, index=True)
- backend/app/models\__init__.py:1243:        UniqueConstraint("sender_user_id", "idempotency_key", name="uq_credit_transfer_sender_idem"),
- backend/app/models\__init__.py:1254:    idempotency_key: str = Field(index=True)
- backend/app/models\__init__.py:1356:        UniqueConstraint("user_id", "idempotency_key", name="uq_credit_holds_user_idempotency"),
- backend/app/models\__init__.py:1363:    idempotency_key: str = Field(index=True, max_length=255)

## Findings
- Positive: explicit timeout, retry/backoff, and idempotency plumbing exists in solve/billing paths.
- Positive: 429/503 responses are implemented for several overload and feature-disabled paths.
- Risk: no end-to-end proof here for retry-storm prevention under upstream brownouts.
- Risk: queue depth SLOs and hard concurrency ceilings are present but not centrally enforced by one guardrail.

## Graceful Failure Mode Status
- Observed in code: fast-fail paths using HTTP 429/503 are present.
- Not fully proven: cascading failure behavior under upstream LLM saturation requires chaos/load injection not included in this run.
