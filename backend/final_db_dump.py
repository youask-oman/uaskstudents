from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv() 

from app.database import engine
from app.models import SystemConfig, PromptAsset, PlanPromptLink, Plan

def dump_everything():
    db_url = os.environ.get('DATABASE_URL', 'default (Postgres)')
    print(f"\nDATABASE SOURCE: {db_url}\n")
    
    with Session(engine) as session:
        # 1. SystemConfig
        print("=== [TABLE: systemconfig] Token Limits & Global Settings ===")
        rows = session.exec(select(SystemConfig).order_by(SystemConfig.key)).all()
        print(f"{'KEY':<50} | {'VALUE':<10} | {'DESCRIPTION'}")
        print("-" * 105)
        for r in rows:
            print(f"{r.key:<50} | {r.value:<10} | {r.description or ''}")
        
        # 2. PromptAsset
        print("\n=== [TABLE: promptasset] AI Prompt Files ===")
        rows = session.exec(select(PromptAsset)).all()
        print(f"{'ID':<3} | {'KEY':<35} | {'KIND':<10} | {'FILE PATH'}")
        print("-" * 105)
        for r in rows:
            print(f"{r.id:<3} | {r.key:<35} | {r.kind:<10} | {r.path}")

        # 3. Plan
        print("\n=== [TABLE: plan] Subscription Tiers ===")
        rows = session.exec(select(Plan)).all()
        print(f"{'ID':<3} | {'NAME':<20} | {'SLUG':<15} | {'FEATURE FLAGS'}")
        print("-" * 105)
        for r in rows:
            print(f"{r.id:<3} | {r.name:<20} | {r.slug:<15} | {r.features}")

        # 4. PlanPromptLink
        print("\n=== [TABLE: planpromptlink] Mode Mapping (Wiring) ===")
        rows = session.exec(select(PlanPromptLink)).all()
        print(f"{'ID':<3} | {'PLAN_ID':<8} | {'MODE':<10} | {'SYS_ASSET_ID':<15} | {'SCH_ASSET_ID'}")
        print("-" * 105)
        for r in rows:
            print(f"{r.id:<3} | {r.plan_id:<8} | {r.mode:<10} | {r.system_prompt_asset_id:<15} | {r.schema_prompt_asset_id}")
        
        print("\n" + "="*105 + "\n")

if __name__ == "__main__":
    dump_everything()
