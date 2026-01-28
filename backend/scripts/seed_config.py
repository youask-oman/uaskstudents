import sys
import os
from pathlib import Path
from sqlmodel import Session, select
from dotenv import load_dotenv

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

env_path = backend_dir.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from app.database import engine
from app.models import SystemConfig
from app.constants.token_policy_defaults import TOKEN_POLICY_DEFAULTS

def seed_config():
    print(f"Seeding SystemConfig table in DB: {os.environ.get('DATABASE_URL', 'default')}")
    with Session(engine) as session:
        for key, (default_val, desc) in TOKEN_POLICY_DEFAULTS.items():
            row = session.get(SystemConfig, key)
            if not row:
                print(f"Creating missing config: {key} = {default_val}")
                row = SystemConfig(key=key, value=str(default_val), description=desc)
                session.add(row)
            else:
                # Optional: Update description if missing
                if not row.description:
                    row.description = desc
                    session.add(row)
                pass # Do not overwrite existing values in a seed script (except initial)
        
        session.commit()
        print("Configuration seeding complete.")

if __name__ == "__main__":
    seed_config()
