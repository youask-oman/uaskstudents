
import sys
import os
from pathlib import Path
from sqlmodel import Session, select

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.database import engine
from app.models import PlanPromptLink, Plan

def check_links():
    with Session(engine) as session:
        plans = session.exec(select(Plan)).all()
        plan_map = {p.id: p.slug for p in plans}
        
        links = session.exec(select(PlanPromptLink)).all()
        print("--- PlanPromptLinks in DB ---")
        for link in links:
            plan_slug = plan_map.get(link.plan_id, f"ID:{link.plan_id}")
            print(f"Plan: {plan_slug}, Mode: {link.mode}, SystemAsset: {link.system_prompt_asset_id}")
        print("------------------------------")

if __name__ == "__main__":
    check_links()
