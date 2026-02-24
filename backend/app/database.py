from sqlmodel import SQLModel, create_engine, Session
from app.models import User, ChatSession, ChatMessage, UsageLog, OCRJob
import os
import time
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


def _build_engine():
    kwargs = {"echo": False}

    if DATABASE_URL.lower().startswith("postgresql"):
        kwargs.update(
            {
                "pool_pre_ping": _bool_env("DB_POOL_PRE_PING", True),
                "pool_size": _int_env("DB_POOL_SIZE", 20),
                "max_overflow": _int_env("DB_MAX_OVERFLOW", 20),
                "pool_timeout": _int_env("DB_POOL_TIMEOUT_SECONDS", 10),
                "pool_recycle": _int_env("DB_POOL_RECYCLE_SECONDS", 1800),
            }
        )

    return create_engine(DATABASE_URL, **kwargs)


engine = _build_engine()

def _ensure_prompt_mode_enum_ocr_extract():
    if not DATABASE_URL.lower().startswith("postgresql"):
        return
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("ALTER TYPE promptmodeenum ADD VALUE IF NOT EXISTS 'OCR_EXTRACT'"))
            logger.info("Ensured promptmodeenum includes OCR_EXTRACT")
    except Exception as e:
        logger.warning(f"Could not ensure promptmodeenum OCR_EXTRACT value: {e}")


def _ensure_solver_attempt_columns() -> None:
    if not DATABASE_URL.lower().startswith("postgresql"):
        return
    ddl = [
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS started_at TIMESTAMP",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMP",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS ttl_deadline_at TIMESTAMP",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS result_json JSON",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS error_json JSON",
        "ALTER TABLE IF EXISTS solveroutputattempt ADD COLUMN IF NOT EXISTS provider_meta JSON",
    ]
    idx = [
        "CREATE INDEX IF NOT EXISTS ix_solver_attempt_started_at ON solveroutputattempt(started_at)",
        "CREATE INDEX IF NOT EXISTS ix_solver_attempt_finished_at ON solveroutputattempt(finished_at)",
        "CREATE INDEX IF NOT EXISTS ix_solver_attempt_cancel_requested_at ON solveroutputattempt(cancel_requested_at)",
        "CREATE INDEX IF NOT EXISTS ix_solver_attempt_ttl_deadline_at ON solveroutputattempt(ttl_deadline_at)",
    ]
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for stmt in ddl:
                conn.execute(text(stmt))
            for stmt in idx:
                conn.execute(text(stmt))
            logger.info("Ensured solveroutputattempt durable columns/indexes")
    except Exception as e:
        logger.warning(f"Could not ensure solveroutputattempt durable columns: {e}")

def create_db_and_tables():
    max_retries = 10
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to database (Attempt {attempt + 1}/{max_retries})...")
            # Try to connect and create tables
            SQLModel.metadata.create_all(engine)
            _ensure_prompt_mode_enum_ocr_extract()
            _ensure_solver_attempt_columns()
            logger.info("Database connection successful and tables created.")
            return
        except OperationalError as e:
            logger.warning(f"Database connection failed: {e}")
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Unexpected error creating database tables: {e}")
            raise e
            
    raise Exception("Could not connect to the database after multiple attempts.")

def get_session():
    with Session(engine) as session:
        yield session

from contextlib import contextmanager

@contextmanager
def get_session_context():
    with Session(engine) as session:
        yield session
