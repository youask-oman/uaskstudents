from sqlmodel import SQLModel, create_engine
import os
from app.models import User, VoiceSession, VoiceAudio, VoiceJob, VoiceArtifact, VoiceConfirmation

# Use environment variable for database URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")

engine = create_engine(DATABASE_URL)

def migrate():
    print(f"Connecting to {DATABASE_URL}...")
    # This will create tables if they don't exist
    # If they exist, it might fail or do nothing depending on the DB state
    # In a production app, use Alembic. 
    # For this foundation, we'll use SQLModel's create_all
    SQLModel.metadata.create_all(engine)
    print("Migration complete. Voice Mode tables ensured.")

if __name__ == "__main__":
    migrate()
