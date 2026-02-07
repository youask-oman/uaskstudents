"""
Migrate SystemErrorEntry table to match new schema.
Adds trace_id, severity, etc.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from sqlmodel import Session, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate():
    with Session(engine) as session:
        try:
            logger.info("Migrating SystemErrorEntry...")
            
            # 1. Add severity column
            logger.info("Adding severity column...")
            session.exec(text("ALTER TABLE systemerrorentry ADD COLUMN IF NOT EXISTS severity VARCHAR DEFAULT 'ERROR'"))
            
            # 2. Backfill severity from level if exists
            logger.info("Backfilling severity from level...")
            # We use a safe update that works even if level is null
            session.exec(text("UPDATE systemerrorentry SET severity = level WHERE level IS NOT NULL"))
            
            # 3. Make level nullable (since we removed it from model)
            logger.info("Making level nullable...")
            session.exec(text("ALTER TABLE systemerrorentry ALTER COLUMN level DROP NOT NULL"))
            
            # 4. Add other new columns
            new_columns = [
                ("error_code", "VARCHAR"),
                ("trace_id", "VARCHAR"),
                ("request_id", "VARCHAR"), 
                ("user_id", "INTEGER"),
                ("fingerprint", "VARCHAR"),
                ("occurrence_count", "INTEGER DEFAULT 1"),
                ("context_json", "JSON"),
                ("last_seen_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]
            
            for col_name, col_type in new_columns:
                logger.info(f"Adding {col_name}...")
                session.exec(text(f"ALTER TABLE systemerrorentry ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            
            # 5. Create indexes
            logger.info("Creating indexes...")
            session.exec(text("CREATE INDEX IF NOT EXISTS ix_systemerrorentry_trace_id ON systemerrorentry(trace_id)"))
            session.exec(text("CREATE INDEX IF NOT EXISTS ix_systemerrorentry_severity ON systemerrorentry(severity)"))
            session.exec(text("CREATE INDEX IF NOT EXISTS ix_systemerrorentry_error_code ON systemerrorentry(error_code)"))
            session.exec(text("CREATE INDEX IF NOT EXISTS ix_systemerrorentry_created_at ON systemerrorentry(created_at)"))

            session.commit()
            logger.info("✓ SystemErrorEntry migration complete")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            session.rollback()
            raise

if __name__ == "__main__":
    migrate()
