"""
Add status and change_reason columns to ProviderModelPricing table.
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
    """Add missing columns to ProviderModelPricing."""
    with Session(engine) as session:
        try:
            # Add status column (default ACTIVE for existing rows)
            logger.info("Adding status column...")
            session.exec(text(
                "ALTER TABLE providermodelpricing ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'ACTIVE'"
            ))
            session.commit()
            logger.info("✓ Added status column")
            
            # Add change_reason column (nullable)
            logger.info("Adding change_reason column...")
            session.exec(text(
                "ALTER TABLE providermodelpricing ADD COLUMN IF NOT EXISTS change_reason VARCHAR"
            ))
            session.commit()
            logger.info("✓ Added change_reason column")
            
            # Create index on status
            logger.info("Creating index on status...")
            session.exec(text(
                "CREATE INDEX IF NOT EXISTS ix_providermodelpricing_status ON providermodelpricing(status)"
            ))
            session.commit()
            logger.info("✓ Created index")
            
            logger.info("\n=== MIGRATION COMPLETE ===")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            session.rollback()
            raise

if __name__ == "__main__":
    migrate()
