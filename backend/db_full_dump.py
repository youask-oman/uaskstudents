from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv() 

from app.database import engine
from app.models import SystemConfig, PromptAsset, PlanPromptLink

def dump_all_config():
    db_url = os.environ.get('DATABASE_URL', 'default (Postgres)')
    print(f"DEBUG: Active Database URL: {db_url}\n")
    
    with Session(engine) as session:
        # Table 1: SystemConfig
        print("--- TABLE: systemconfig (Token Limits) ---")
        rows = session.exec(select(SystemConfig)).all()
        if not rows: print(" EMPTY")
        else:
            print(f"{'Key':<45} | {'Value':<10}")
            print("-" * 60)
            for r in rows: print(f"{r.key:<45} | {r.value:<10}")
        
        # Table 2: PromptAsset
        print("\n--- TABLE: promptasset (AI Tooling) ---")
        rows = session.exec(select(PromptAsset)).all()
        if not rows: print(" EMPTY - This is the root cause! Detailed mode requires assets.")
        else:
            print(f"{'Key':<35} | {'Kind':<10} | {'Path'}")
            print("-" * 75)
            for r in rows: print(f"{r.key:<35} | {r.kind:<10} | {r.path}")

        # Table 3: PlanPromptLink
        print("\n--- TABLE: planpromptlink (Subscription Mapping) ---")
        rows = session.exec(select(PlanPromptLink)).all()
        if not rows: print(" EMPTY - This prevents the system from mapping your plan to mode.")
        else:
            print(f"{'ID':<3} | {'PlanID':<6} | {'Mode':<10} | {'System':<10} | {'Schema':<10}")
            print("-" * 50)
            for r in rows: print(f"{r.id:<3} | {r.plan_id:<6} | {r.mode:<10} | {r.system_prompt_asset_id:<10} | {r.schema_prompt_asset_id:<10}")
        print("\n============================================\n")

if __name__ == "__main__":
    dump_all_config()
