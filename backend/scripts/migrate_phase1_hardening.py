import sys
import os
from sqlmodel import Session, create_engine, text

# Add backend directory to path so we can import app if needed (though using raw SQL here)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# from app.config import get_settings # Removed

def migrate():
    # settings = get_settings() # Removed
    database_url = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(database_url)
    
    # We use raw SQL to ALTER results table for the new columns
    # We need to add:
    # - llm_responses (JSONB)
    # - validation_events (JSONB)
    # - input_tokens (Integer)
    # - output_tokens (Integer)
    # - total_tokens (Integer)
    
    statements = [
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS llm_responses JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS validation_events JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS input_tokens INTEGER DEFAULT 0;",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS output_tokens INTEGER DEFAULT 0;",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0;"
    ]
    
    print("--- Starting Phase 1 Hardening Migration ---")
    with Session(engine) as session:
        for stmt in statements:
            print(f"Executing: {stmt}")
            try:
                session.connection().execute(text(stmt))
                session.commit()
                print("  -> Success")
            except Exception as e:
                print(f"  -> Failed (may already exist or error): {e}")
                session.rollback()
                
    print("--- Migration Complete ---")

if __name__ == "__main__":
    migrate()
