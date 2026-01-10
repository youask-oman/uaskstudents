from sqlmodel import create_engine, text
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = "sqlite:///./backend/app.db"
engine = create_engine(DATABASE_URL)

def migrate_session():
    logger.info("Starting session & IP migration...")
    
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
    
    logger.info("Migration complete.")

if __name__ == "__main__":
    migrate_session()
