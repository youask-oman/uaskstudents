import os
from sqlalchemy import create_engine, text

# Get DB URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_migration():
    print(f"Running Phase 1 Migration on {DATABASE_URL.split('@')[-1]}...")
    
    # List of ALTER statements to add new columns
    # We use IF NOT EXISTS logic implicitly by catching duplicates or being careful
    # But easier to just try/except each or use IF NOT EXISTS if PG supports it for columns (PG 9.6+ does)
    
    statements = [
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS attempt_id VARCHAR",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS prompt_meta JSONB",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS input_text_raw TEXT",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS input_text_normalized TEXT",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS llm_raw_response JSONB",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS validation_errors JSONB",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS clarification_count INTEGER DEFAULT 0",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS clarification_history JSONB",
        "ALTER TABLE solveroutputattempt ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()",
        
        # Update existing columns if needed (status is already varchar, just adding new enum logic effectively)
        # Create index on attempt_id
         "CREATE INDEX IF NOT EXISTS ix_solveroutputattempt_attempt_id ON solveroutputattempt (attempt_id)",
         
        # Ensure status index exists (should already be there from model)
    ]
    
    # Helper for SQLite vs Postgres
    is_sqlite = "sqlite" in DATABASE_URL
    
    with engine.connect() as conn:
        for stmt in statements:
            try:
                if is_sqlite:
                    # SQLite has limited ALTER support, might fail on complex ones or indexes
                    # But we'll try simple adds. 
                    # For JSONB in sqlite we use JSON or TEXT
                    stmt = stmt.replace("JSONB", "JSON")
                    if "ADD COLUMN IF NOT EXISTS" not in stmt: # SQLite supports it in newer versions, but...
                         pass 
                
                print(f"Executing: {stmt}")
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                print(f"Error (ignoring): {e}")

    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
