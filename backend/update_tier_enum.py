from sqlalchemy import text
from app.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_prompt_tier_enum():
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Postgres doesn't allow IF NOT EXISTS for ADD VALUE in some versions within transactions, 
            # but usually it works fine with execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("ALTER TYPE prompttierenum ADD VALUE IF NOT EXISTS 'SHORT'"))
            logger.info("Successfully added 'SHORT' to prompttierenum")
    except Exception as e:
        logger.error(f"Failed to update prompttierenum: {e}")

if __name__ == "__main__":
    update_prompt_tier_enum()
