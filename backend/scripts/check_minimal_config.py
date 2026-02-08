import sys
import os
from sqlmodel import Session, select
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Force Postgres URL
os.environ["DATABASE_URL"] = "postgresql://uask_user:uask_password@localhost:5432/uask_db"

from app.database import engine
from app.models import SystemConfig

def check_config():
    with Session(engine) as session:
        key = "tokens.text.output_max_minimal_solve"
        statement = select(SystemConfig).where(SystemConfig.key == key)
        config = session.exec(statement).first()
        if config:
            print(f"Current value for {key}: {config.value}")
        else:
            print(f"Key {key} NOT FOUND")

if __name__ == "__main__":
    check_config()
