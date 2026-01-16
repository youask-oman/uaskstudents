from fastapi import FastAPI, Request
from app.database import create_db_and_tables, get_session
from sqlmodel import Session, select
import logging
import json
import time
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api import limiter

app = FastAPI(title="UAsk.ai Orchestrator")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware

import os
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
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
    if not root_logger.handlers:
        handler = logging.StreamHandler()
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
        
        # Only use JSON in production/docker environments
        if os.environ.get("USE_JSON_LOGGING") == "true":
            handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)
    
    create_db_and_tables()

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

from app.api import api_router
app.include_router(api_router, prefix="/api/v1")

from fastapi.staticfiles import StaticFiles
import os

# Mount storage for uploads and OCR assets
if not os.path.exists("storage"):
    os.makedirs("storage")
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/")
def read_root():
    return {"status": "ok", "service": "UAsk.ai Orchestrator v1"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}
