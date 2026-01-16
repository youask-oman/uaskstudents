
from sqlmodel import create_engine, text
import os

# Use localhost if running from host, or service name if running from container
# Since I'll run this likely via "docker compose run", I'll use service name or default
# But wait, run_command runs on HOST. Host can't access postgres:5432 directly unless exposed.
# docker-compose.yml exposes 5432:5432.
# So I can use localhost:5432.
DATABASE_URL = "postgresql://uask_user:uask_password@localhost:5432/uask_db"

def migrate():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("Dropping canonical tables to force schema update...")
            conn.execute(text("DROP TABLE IF EXISTS canonicalsolution CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS canonicalproblem CASCADE;"))
            conn.commit()
            print("Tables dropped successfully.")
    except Exception as e:
        print(f"Migration failed (is DB running?): {e}")

if __name__ == "__main__":
    migrate()
