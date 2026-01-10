import sys
import os

# Add root to path so we can import backend.app
sys.path.append(os.getcwd())

# Import engine directly from the app configuration
try:
    from backend.app.database import engine
except ImportError:
    # Fallback if running from backend dir
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from app.database import engine

from sqlmodel import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    logger.info(f"Targeting Database: {engine.url}")
    with engine.connect() as connection:
        # Check and add session_token column
        try:
            logger.info("Adding session_token column...")
            connection.execute(text('ALTER TABLE "user" ADD COLUMN session_token VARCHAR'))
            logger.info("Added session_token successfully.")
        except Exception as e:
            logger.warning(f"session_token column might already exist: {e}")
            
        # Check and add last_ip column
        try:
            logger.info("Adding last_ip column...")
            connection.execute(text('ALTER TABLE "user" ADD COLUMN last_ip VARCHAR'))
            logger.info("Added last_ip successfully.")
        except Exception as e:
            logger.warning(f"last_ip column might already exist: {e}")
            
        connection.commit()

if __name__ == "__main__":
    migrate()
