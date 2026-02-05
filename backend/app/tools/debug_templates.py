
import os
import sys
from pathlib import Path
from sqlmodel import Session, create_engine, select

# Setup path
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env
from dotenv import load_dotenv
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

# Force DB URL
os.environ["DATABASE_URL"] = "postgresql://uask_user:uask_password@localhost:5432/uask_db"

from app.database import engine
from app.models import PromptTemplateEntry, PromptTierEnum

def dump_templates():
    with Session(engine) as session:
        print("--- DUMP TEMPLATES (solve_standard_v1) ---")
        entries = session.exec(select(PromptTemplateEntry).where(
            PromptTemplateEntry.prompt_id == "solve_standard_v1"
        )).all()
        
        for entry in entries:
            print(f"ID: {entry.id}")
            print(f"  Prompt ID: {entry.prompt_id}")
            print(f"  Tier: {entry.tier}")
            print(f"  Version: {entry.version}")
            print(f"  Active: {entry.is_active}")
            print(f"  Content Len: {len(entry.content) if entry.content else 0}")
            print("-" * 40)
            
        print(f"Total entries found: {len(entries)}")
        
if __name__ == "__main__":
    dump_templates()
