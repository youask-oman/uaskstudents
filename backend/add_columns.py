from sqlmodel import create_engine, text
import os

# Get DB URL from env or default
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_migration():
    # We open a new connection for each statement to avoid "current transaction is aborted"
    
    alter_statements = [
        "ALTER TABLE chatmessage ADD COLUMN subject VARCHAR",
        "ALTER TABLE chatmessage ADD COLUMN grade_level VARCHAR",
        "ALTER TABLE chatmessage ADD COLUMN difficulty VARCHAR",
        "ALTER TABLE chatmessage ADD COLUMN topics JSONB"
    ]
    
    # Check if we should use JSON or JSONB based on simple string check
    if "sqlite" in DATABASE_URL:
         alter_statements[-1] = "ALTER TABLE chatmessage ADD COLUMN topics JSON"

    for stmt in alter_statements:
        try:
            with engine.connect() as conn:
                print(f"Executing: {stmt}")
                conn.execute(text(stmt))
                conn.commit()
                print("Success.")
        except Exception as e:
            print(f"Skipped/Failed (probably exists): {e}")

if __name__ == "__main__":
    run_migration()
