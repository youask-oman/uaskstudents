from dotenv import load_dotenv
# Ensure .env is loaded before importing modules that read settings.
load_dotenv()

import sys
import io

# Windows consoles often default to cp1252 and crash on symbols like "≠".
# Force UTF-8 early so all stream-based logging can emit safely.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _make_utf8_stream(stream):
    if stream is None:
        return stream
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            return stream
        except Exception:
            pass
    if hasattr(stream, "buffer"):
        try:
            return io.TextIOWrapper(
                stream.buffer,
                encoding="utf-8",
                errors="replace",
                write_through=True,
            )
        except Exception:
            return stream
    return stream


def _harden_logging_stream_encodings() -> None:
    for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "openai", "openai._base_client"):
        logger_obj = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        for handler in logger_obj.handlers:
            stream = getattr(handler, "stream", None)
            if stream is None:
                continue
            patched = _make_utf8_stream(stream)
            if patched is not None and patched is not stream:
                try:
                    handler.setStream(patched)
                except Exception:
                    pass

from fastapi import FastAPI, Request
from app.database import create_db_and_tables, get_session
from sqlmodel import Session, select
import logging
import json
import time
import uuid
import asyncio
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api import limiter
from pathlib import Path
from app.services.llm import get_llm_manager
from app.services.llm.manager import get_configured_openai_model, get_configured_ollama_model
from app.services.math_render_service import get_math_render_service
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from app.config import get_settings
from jose import JWTError, jwt
from app.auth import SECRET_KEY, ALGORITHM
from app.services.legal_service import get_terms_requirement_status

app = FastAPI(title="UAsk.ai Orchestrator")
app.state.limiter = limiter
logger = logging.getLogger("app")
_harden_logging_stream_encodings()


async def _start_math_render_safely() -> None:
    try:
        await get_math_render_service().startup()
    except NotImplementedError:
        logging.warning(
            "Math render startup skipped: event loop does not support subprocesses on this runtime."
        )
    except Exception:
        logging.exception("Failed to start math render service")

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    from app.trace import TraceContext
    logger = logging.getLogger("api")
    logger.info(f"Response: {exc.status_code} | {exc.detail}", extra=TraceContext.get_all())
    request_id = TraceContext.get().request_id if hasattr(TraceContext, 'get') else None
    status_code = exc.status_code
    code_map = {
        400: "bad_request",
        401: "auth_required",
        402: "insufficient_credits",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit",
    }
    message = exc.detail if isinstance(exc.detail, str) else (exc.detail.get("message") if isinstance(exc.detail, dict) else "Request failed")
    error_payload = {
        "error": {
            "code": code_map.get(status_code, "http_error"),
            "message": message,
            "request_id": request_id,
            "details": exc.detail if not isinstance(exc.detail, str) else None,
        },
        "detail": exc.detail,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from app.trace import TraceContext
    logger = logging.getLogger("api")
    logger.info(f"Response: 422 | Validation Error", extra=TraceContext.get_all())
    request_id = TraceContext.get().request_id if hasattr(TraceContext, 'get') else None
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Validation error",
                "request_id": request_id,
                "details": exc.errors(),
            },
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    from app.trace import TraceContext
    logger = logging.getLogger("api")
    logger.error(f"Response: 500 | Unhandled Error: {str(exc)}", exc_info=True, extra=TraceContext.get_all())
    request_id = TraceContext.get().request_id if hasattr(TraceContext, 'get') else None
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal Server Error",
                "request_id": request_id,
                "details": None,
            },
            "detail": "Internal Server Error",
            "request_id": request_id,
        },
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware
import os

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|\[::1\])(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*", "X-Request-ID"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    from app.trace import TraceContext
    import uuid
    
    start_time = time.perf_counter()
    
    # Trace ID is the primary correlation across all logs
    trace_id = str(uuid.uuid4())
    # Request ID might come from header or be specific to the solver
    request_id = request.headers.get("X-Request-ID")
    
    # Initialize TraceContext for this async task
    TraceContext.set(trace_id=trace_id, request_id=request_id)
    
    logger = logging.getLogger("api")
    logger.info(f"Incoming: {request.method} {request.url.path}", extra=TraceContext.get_all())
    
    try:
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Merge any updated context (e.g. user_id set during auth)
        context = TraceContext.get_all()
        # Normal responses are logged here. Error responses from exception_handlers will be logged there.
        if response.status_code < 400:
            logger.info(f"Response: {response.status_code} | {duration_ms}ms", extra=context)
        
        response.headers["X-Trace-ID"] = trace_id
        if request_id:
            response.headers["X-Request-ID"] = request_id
            
        return response
    except Exception as e:
        # Exceptions that escape handlers are logged here as a last resort
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        # We don't log error here if it's already logged by an exception handler 
        # but since we re-raise, FastAPI will call the handlers.
        raise e


@app.middleware("http")
async def enforce_terms_acceptance(request: Request, call_next):
    async def _safe_call_next():
        try:
            return await call_next(request)
        except RuntimeError as exc:
            if "No response returned." in str(exc):
                logging.getLogger("app").exception(
                    "terms_acceptance_no_response path=%s method=%s",
                    request.url.path,
                    request.method,
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": "internal_error",
                            "message": "Request failed before a response was produced.",
                        }
                    },
                )
            raise

    path = request.url.path or ""
    if not path.startswith("/api/"):
        return await _safe_call_next()

    # Allow auth + public/legal endpoints and health checks through.
    allow_prefixes = (
        "/api/v1/login",
        "/api/v1/signup",
        "/api/legal/",
        "/api/admin/legal-documents",
        "/health",
        "/ready",
    )
    if any(path.startswith(prefix) for prefix in allow_prefixes):
        return await _safe_call_next()

    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return await _safe_call_next()

    token = auth.replace("Bearer ", "").strip()
    email = None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return await _safe_call_next()
    except JWTError:
        return await _safe_call_next()

    from app.database import engine
    from app.models import User

    try:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == email)).first()
            if user and user.role not in {"admin", "superadmin", "devops", "support", "finance"}:
                required, required_version = get_terms_requirement_status(session, user_id=user.id)
                if required:
                    return JSONResponse(
                        status_code=428,
                        content={
                            "error": {
                                "code": "terms_acceptance_required",
                                "message": "You must accept the latest Terms of Service before continuing.",
                                "details": {
                                    "document_key": "terms_of_service",
                                    "document_version": required_version,
                                },
                            }
                        },
                    )
    except Exception:
        # Fail open to avoid breaking production traffic on policy-check errors.
        # Continue to downstream handler once.
        logging.getLogger("app").exception("terms_acceptance_middleware_error")

    return await _safe_call_next()

@app.on_event("startup")
def on_startup():
    _harden_logging_stream_encodings()
    # Configure Structured Logging
    root_logger = logging.getLogger()
    json_logging = os.environ.get("USE_JSON_LOGGING") == "true"

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
            }
            # Include trace fields if present in record
            for field in ["trace_id", "request_id", "user_id", "subscription_id", "attempt_id", "phase", "status"]:
                if hasattr(record, field):
                    log_record[field] = getattr(record, field)
                elif hasattr(record, "extra") and field in record.extra:
                    log_record[field] = record.extra[field]

            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    formatter = JsonFormatter() if json_logging else None

    log_level_name = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    root_logger.setLevel(getattr(logging, log_level_name, logging.INFO))
    if not root_logger.handlers:
        handler = logging.StreamHandler(_make_utf8_stream(sys.stderr))
        if formatter:
            handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    log_to_file = os.environ.get("ENABLE_DEBUG_LOGS", "true").lower() in {"1", "true", "yes"}
    log_path = Path(os.environ.get("DEBUG_LOG_PATH", "backend/debug_logs.txt"))
    if log_to_file:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        existing_file_handler = any(
            isinstance(handler, logging.FileHandler)
            and Path(getattr(handler, "baseFilename", "")).resolve() == log_path.resolve()
            for handler in root_logger.handlers
        )
        if not existing_file_handler:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            if formatter:
                file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    create_db_and_tables()
    
    # Initialize Plans
    from app.services.subscription_service import subscription_service
    from app.services.prompt_registry_service import prompt_registry_service
    from app.database import engine
    from sqlmodel import Session
    with Session(engine) as session:
        try:
            subscription_service.ensure_plans_exist(session)
        except Exception as e:
            logging.error(f"Failed to initialize plans: {e}")
            session.rollback()

        bootstrap_from_files = os.environ.get("PROMPT_REGISTRY_BOOTSTRAP_FROM_FILES", "false").lower() in {"1", "true", "yes"}
        if bootstrap_from_files:
            logging.warning("Prompt registry bootstrap from files is deprecated. Use admin UI to manage prompts.")
        else:
            logging.info("Prompt registry bootstrap from files is disabled; using DB-only prompts/schemas.")

        strict_binding_matrix = os.environ.get("PROMPT_REGISTRY_AUDIT_EXPECT_FULL_MATRIX", "false").lower() in {"1", "true", "yes"}
        try:
            report = prompt_registry_service.audit_active_bindings(
                session,
                expect_full_matrix=strict_binding_matrix,
            )
            if report.get("ok"):
                logging.info(
                    "Prompt binding integrity OK: active_bindings=%s active_pairs=%s",
                    report.get("active_bindings"),
                    report.get("active_binding_pairs"),
                )
            else:
                logging.warning(
                    "Prompt binding integrity issues found: %s issue(s)",
                    len(report.get("issues", [])),
                )
                for issue in report.get("issues", [])[:20]:
                    logging.warning("Prompt binding issue: %s", issue)
        except Exception as e:
            logging.error(f"Failed to audit prompt bindings: {e}")
            session.rollback()

    if os.environ.get("DISABLE_OPENAI", "").lower() not in {"1", "true", "yes"}:
        _ = get_llm_manager()
    else:
        logging.info("DISABLE_OPENAI is enabled; skipping LLM manager initialization")

    if os.environ.get("DISABLE_MATH_RENDER", "").lower() in {"1", "true", "yes"}:
        logging.info("DISABLE_MATH_RENDER is enabled; skipping math render service startup")
    else:
        try:
            # Start backend-only MathJax worker pool.
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_start_math_render_safely())
            except RuntimeError:
                asyncio.run(_start_math_render_safely())
        except Exception as e:
            logging.error("Failed to schedule math render service startup: %s", e)


@app.on_event("shutdown")
async def on_shutdown():
    try:
        await get_math_render_service().shutdown()
    except Exception as e:
        logging.warning("Math render shutdown warning: %s", e)


# Monitoring Endpoints
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/ready")
def readiness_check():
    # Check DB
    try:
        from app.database import engine
        from sqlmodel import Session, text
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503

@app.get("/health/llm")
async def llm_health_check():
    manager = get_llm_manager()
    openai = await manager.check_openai()
    ollama = await manager.check_ollama()
    breaker = manager.get_circuit_breaker_state("openai")
    try:
        openai_model = get_configured_openai_model()
    except Exception as exc:
        openai_model = f"unavailable: {str(exc)}"
    ollama_model = get_configured_ollama_model()
    ollama_final_model = get_configured_ollama_model("FINAL")
    return {
        "provider": manager.primary_provider,
        "fallback_enabled": manager.fallback_enabled,
        "models": {
            "openai_default": openai_model,
            "ollama_default": ollama_model,
            "ollama_final": ollama_final_model,
        },
        "openai": openai,
        "ollama": ollama,
        "circuit_breaker": breaker,
        "last_error": manager.last_error,
        "timestamp": time.time(),
    }

from app.api import api_router
from app.api_admin import admin_router, legal_router
from app.api_admin_payments import router as admin_payments_router
from app.api_topups import router as topup_router
from app.api_stripe import router as stripe_router
from app.api_billing import router as billing_router
from app.api_wallet import router as wallet_router
from app.api_admin_payments_config import router as admin_payments_config_router
from app.api_admin_health import router as admin_health_router
from app.api_admin_content import router as admin_content_router
from app.api_admin_ocr_config import router as admin_ocr_config_router
from app.api_admin_credits import router as admin_credits_router, prompt_bindings_router as admin_prompt_bindings_router

# Billing Admin APIs
from app.admin_billing.billing_flags import (
    router as billing_flags_router,
    legacy_router as billing_flags_legacy_router,
)
from app.admin_billing.billing_programs import router as billing_programs_router
from app.admin_billing.billing_wallet import router as billing_wallet_router
from app.admin_billing.billing_holds import router as billing_holds_router
from app.admin_billing.billing_refunds import router as billing_refunds_router
from app.admin_billing.billing_health import router as billing_health_router
from app.admin_billing.billing_ledger import router as billing_ledger_router
from app.admin_billing.billing_invoices import router as billing_invoices_router
from app.admin_billing.billing_pricing import router as billing_pricing_router
from app.admin_billing.billing_packs import router as billing_packs_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(topup_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")

@app.on_event("startup")
async def log_stripe_env():
    settings = get_settings()
    key = settings.STRIPE_SECRET_KEY or ""
    masked = ""
    if key:
        masked = f"{key[:7]}***{key[-4:]}" if len(key) > 11 else "***"
    logger.info(
        "Stripe env loaded: STRIPE_SECRET_KEY=%s STRIPE_LIVE_MODE=%s",
        "SET" if key else "MISSING",
        settings.STRIPE_LIVE_MODE,
    )
    if key:
        logger.info("Stripe key masked: %s", masked)
app.include_router(billing_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(admin_router)
app.include_router(legal_router)
app.include_router(admin_payments_router)
app.include_router(admin_payments_config_router)
app.include_router(admin_health_router)
app.include_router(admin_content_router)
app.include_router(admin_ocr_config_router)
app.include_router(admin_credits_router)
app.include_router(admin_prompt_bindings_router)

# Billing Admin Routers
app.include_router(billing_flags_router)
app.include_router(billing_flags_legacy_router)
app.include_router(billing_programs_router)
app.include_router(billing_wallet_router)
app.include_router(billing_holds_router)
app.include_router(billing_refunds_router)
app.include_router(billing_health_router)
app.include_router(billing_ledger_router)
app.include_router(billing_invoices_router)
app.include_router(billing_pricing_router)
app.include_router(billing_packs_router)

from fastapi.staticfiles import StaticFiles
import os

# Mount storage for uploads and OCR assets
if not os.path.exists("storage"):
    os.makedirs("storage")
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/")
def read_root():
    return {"status": "ok", "service": "UAsk.ai Orchestrator v1"}

# Reload trigger 8
