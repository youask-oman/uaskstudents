
import sys
import os
from pathlib import Path
from sqlmodel import Session, select

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.database import engine
from app.models import PromptAsset

def check_assets():
    with Session(engine) as session:
        rows = session.exec(select(PromptAsset)).all()
        print("--- PromptAssets in DB ---")
        for row in rows:
            print(f"ID: {row.id}, Key: {row.key}, Path: {row.path}")
        print("---------------------------")

if __name__ == "__main__":
    check_assets()
