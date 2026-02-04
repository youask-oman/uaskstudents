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

engine = create_engine(DATABASE_URL, echo=False)

def _ensure_prompt_mode_enum_ocr_extract():
    if not DATABASE_URL.lower().startswith("postgresql"):
        return
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("ALTER TYPE promptmodeenum ADD VALUE IF NOT EXISTS 'OCR_EXTRACT'"))
            logger.info("Ensured promptmodeenum includes OCR_EXTRACT")
    except Exception as e:
        logger.warning(f"Could not ensure promptmodeenum OCR_EXTRACT value: {e}")

def create_db_and_tables():
    max_retries = 10
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to database (Attempt {attempt + 1}/{max_retries})...")
            # Try to connect and create tables
            SQLModel.metadata.create_all(engine)
            _ensure_prompt_mode_enum_ocr_extract()
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
