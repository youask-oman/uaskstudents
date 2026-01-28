
import sys
import os
from pathlib import Path
from sqlmodel import Session, select

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.database import engine
from app.models import Plan

def check_plans():
    with Session(engine) as session:
        rows = session.exec(select(Plan)).all()
        print("--- Plans in DB ---")
        for row in rows:
            # Use getattr to be safe
            slug = getattr(row, "slug", "N/A")
            features = getattr(row, "features", {})
            print(f"ID: {row.id}, Slug: {slug}, Features: {features}")
        print("-------------------")

if __name__ == "__main__":
    check_plans()
