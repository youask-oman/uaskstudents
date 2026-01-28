
import sys
import os
from pathlib import Path
from sqlmodel import Session, select

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.database import engine
from app.models import SystemConfig

def check_limits():
    with Session(engine) as session:
        rows = session.exec(select(SystemConfig)).all()
        print("--- SystemConfig in DB ---")
        for row in rows:
            if "token" in row.key:
                print(f"{row.key}: {row.value}")
        print("--------------------------")

if __name__ == "__main__":
    check_limits()
