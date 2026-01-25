from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

# Load env vars from parent dir if needed
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv() # Fallback search

from app.database import engine
from app.models import SystemConfig

def update_tokens():
    print(f"Connecting to DB: {os.environ.get('DATABASE_URL', 'default')}")
    with Session(engine) as session:
        updates = {
            "tokens.text.output_max_detailed_solve": "3000",
            "tokens.text.output_max_detailed_study": "3500",
            "tokens.text.output_retry_cap_detailed_solve": "3200",
            "tokens.text.output_retry_cap_detailed_study": "3600"
        }
        
        print("Checking SystemConfig tokens...")
        for key, new_val in updates.items():
            row = session.get(SystemConfig, key)
            if row:
                current_val = int(row.value)
                target_val = int(new_val)
                if current_val < target_val:
                    print(f"Updating {key}: {current_val} -> {target_val}")
                    row.value = new_val
                    session.add(row)
                else:
                    print(f"Verified {key}: {current_val} >= {target_val}")
            else:
                print(f"Creating {key}: {new_val}")
                row = SystemConfig(key=key, value=new_val)
                session.add(row)
        
        session.commit()
        print("Token update complete.")

if __name__ == "__main__":
    update_tokens()
