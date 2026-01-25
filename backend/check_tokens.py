from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

# Load env vars from parent dir if needed
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv() 

from app.database import engine
from app.models import SystemConfig

def check_tokens():
    print(f"Connecting to DB: {os.environ.get('DATABASE_URL', 'default')}")
    with Session(engine) as session:
        keys = [
            "tokens.text.output_max_detailed_solve",
            "tokens.text.output_max_detailed_study",
            "tokens.text.output_retry_cap_detailed_solve",
            "tokens.text.output_retry_cap_detailed_study",
            "tokens.text.output_max_minimal_solve"
        ]
        
        print("--- Current DB Values ---")
        for key in keys:
            row = session.get(SystemConfig, key)
            val = row.value if row else "MISSING"
            print(f"{key}: {val}")
        print("-------------------------")

if __name__ == "__main__":
    check_tokens()
