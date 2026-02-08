import sys
import os
from sqlmodel import Session, select
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(env_path)

# Force Postgres URL
os.environ["DATABASE_URL"] = "postgresql://uask_user:uask_password@localhost:5432/uask_db"

from app.database import engine
from app.models import SystemConfig

def update_config():
    print(f"Connecting to DB...")
    with Session(engine) as session:
        key = "tokens.text.output_max_detailed_solve"
        statement = select(SystemConfig).where(SystemConfig.key == key)
        config = session.exec(statement).first()
        
        if not config:
            print(f"Config key {key} not found! Creating it...")
            config = SystemConfig(key=key, value="4000")
            session.add(config)
        else:
            print(f"Updating {key} from {config.value} to 4000")
            config.value = "4000"
            session.add(config)
            
        session.commit()
        print("Successfully updated config.")

if __name__ == "__main__":
    update_config()
