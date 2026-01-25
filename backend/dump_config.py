from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

# Setup environment
backend_dir = Path(__file__).parent.parent
# Load env vars from parent dir if needed (matches main.py behavior if run from backend)
load_dotenv() 

from app.database import engine
from app.models import SystemConfig

def dump_config():
    # Mask password for security
    db_url = os.environ.get('DATABASE_URL', 'default (Postgres)')
    print(f"DEBUG: Connecting to {db_url}")
    
    with Session(engine) as session:
        statement = select(SystemConfig)
        results = session.exec(statement).all()
        
        print("\n=== SYSTEM CONFIGURATION TABLE ===")
        print(f"{'Key':<45} | {'Value':<10} | {'Description'}")
        print("-" * 100)
        for row in results:
            print(f"{row.key:<45} | {row.value:<10} | {row.description or ''}")
        print("===================================\n")

if __name__ == "__main__":
    dump_config()
