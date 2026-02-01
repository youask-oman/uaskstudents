from fastapi import FastAPI, Request
from dotenv import load_dotenv
from app.database import create_db_and_tables, get_session
from sqlmodel import Session, select
import logging
import json
import time
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api import limiter
from pathlib import Path
from app.services.llm import get_llm_manager

load_dotenv()

app = FastAPI(title="UAsk.ai Orchestrator")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware
import os

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|\[::1\])(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)



@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("uvicorn")
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        raise e

@app.on_event("startup")
def on_startup():
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
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    formatter = JsonFormatter() if json_logging else None

    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
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
    from app.database import engine
    from sqlmodel import Session
    with Session(engine) as session:
        try:
            subscription_service.ensure_plans_exist(session)
        except Exception as e:
            logging.error(f"Failed to initialize plans: {e}")

    manager = get_llm_manager()
    if manager.primary_provider == "ollama":
        probe = manager.check_ollama_sync(timeout_seconds=2.0)
        if not probe.get("reachable"):
            logging.getLogger("uvicorn").warning(
                "OLLAMA STARTUP SELF-CHECK FAILED: base_url=%s error=%s",
                probe.get("base_url"),
                probe.get("error"),
            )

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
    ollama = await manager.check_ollama()
    openai = await manager.check_openai()
    breaker = manager.get_circuit_breaker_state("ollama")
    return {
        "provider": manager.primary_provider,
        "fallback_enabled": manager.fallback_enabled,
        "models": {
            "ollama_default": os.environ.get("OLLAMA_MODEL_DEFAULT", "mightykatun/qwen2.5-math:7b"),
            "openai_default": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
        },
        "ollama": ollama,
        "openai": openai,
        "circuit_breaker": breaker,
        "last_error": manager.last_error,
        "timestamp": time.time(),
    }

from app.api import api_router
from app.api_admin import admin_router
app.include_router(api_router, prefix="/api/v1")
app.include_router(admin_router)

from fastapi.staticfiles import StaticFiles
import os

# Mount storage for uploads and OCR assets
if not os.path.exists("storage"):
    os.makedirs("storage")
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/")
def read_root():
    return {"status": "ok", "service": "UAsk.ai Orchestrator v1"}
