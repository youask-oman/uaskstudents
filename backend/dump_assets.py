from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv() 

from app.database import engine
from app.models import PromptAsset

def dump_assets():
    print(f"DEBUG: Connecting to {os.environ.get('DATABASE_URL', 'default')}")
    with Session(engine) as session:
        statement = select(PromptAsset)
        results = session.exec(statement).all()
        
        print("\n=== PROMPT ASSETS TABLE ===")
        print(f"{'Key':<30} | {'Kind':<10} | {'Path'}")
        print("-" * 80)
        for row in results:
            print(f"{row.key:<30} | {row.kind:<10} | {row.path}")
        print("===========================\n")

if __name__ == "__main__":
    dump_assets()
