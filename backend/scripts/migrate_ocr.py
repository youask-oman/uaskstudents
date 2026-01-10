import os
import logging
from sqlmodel import create_engine, text, Session, select
from app.models import SQLModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
engine = create_engine(DATABASE_URL)

def migrate_ocr():
    logger.info("Starting OCR Subsystem migration...")
    
    # 1. Create new tables
    logger.info("Creating new tables...")
    SQLModel.metadata.create_all(engine)
    
    # 2. Update OCRJob table (Add missing columns if not present)
    new_columns = [
        ("crop_id", "INTEGER"),
        ("requested_engine", "VARCHAR"),
        ("priority", "VARCHAR"),
        ("attempts", "INTEGER DEFAULT 0"),
        ("error_code", "VARCHAR"),
        ("error_message", "TEXT"),
        ("started_at", "TIMESTAMP"),
        ("finished_at", "TIMESTAMP"),
    ]
    
    with engine.connect() as connection:
        for col_name, col_type in new_columns:
            try:
                logger.info(f"Adding column {col_name} to ocrjob...")
                connection.execute(text(f'ALTER TABLE ocrjob ADD COLUMN {col_name} {col_type}'))
                logger.info(f"Added {col_name} successfully.")
            except Exception as e:
                logger.warning(f"Column {col_name} might already exist or error: {e}")
        
        # Also handle potential removal of old columns if desired, but let's keep them for safety
        # and just ensure nullable if they were required
        
        connection.commit()
    
    logger.info("Migration complete.")

if __name__ == "__main__":
    migrate_ocr()
