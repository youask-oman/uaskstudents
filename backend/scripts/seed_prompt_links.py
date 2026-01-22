
import sys
import os
import hashlib
from sqlmodel import Session, select, SQLModel

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import PromptAsset, PlanPromptLink, Plan, User

def compute_checksum(filepath):
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def seed_assets(session):
    print("Seeding Prompt Assets...")
    assets = [
        # Shared Minimal
        {"key": "shared:minimal_system", "kind": "system", "path": "llm_profiles/shared/minimal_system.txt"},
        {"key": "shared:minimal_schema", "kind": "schema", "path": "llm_profiles/shared/minimal_schema.json"},
        # Shared Detailed
        {"key": "shared:detailed_system", "kind": "system", "path": "llm_profiles/shared/detailed_system.txt"},
        {"key": "shared:canonical_schema", "kind": "schema", "path": "llm_profiles/shared/canonical_schema.json"},
        # Free Tier
        {"key": "free:system", "kind": "system", "path": "llm_profiles/free/system.txt"},
        {"key": "free:schema", "kind": "schema", "path": "llm_profiles/free/schema.json"},
    ]

    asset_map = {} # key -> id

    for a in assets:
        # Path relative to backend/app
        # Script assumed to run from backend root
        relative_path = os.path.join("app", a["path"])
        
        if not os.path.exists(relative_path):
            print(f"Warning: Asset file not found: {relative_path}")
            continue
            
        checksum = compute_checksum(relative_path)
        
        existing = session.exec(select(PromptAsset).where(PromptAsset.key == a["key"])).first()
        if existing:
            existing.checksum = checksum
            existing.path = a["path"]
            session.add(existing)
            session.commit()
            session.refresh(existing)
            asset_map[a["key"]] = existing.id
            print(f"Updated asset: {a['key']}")
        else:
            new_asset = PromptAsset(key=a["key"], kind=a["kind"], path=a["path"], checksum=checksum)
            session.add(new_asset)
            session.commit()
            session.refresh(new_asset)
            asset_map[a["key"]] = new_asset.id
            print(f"Created asset: {a['key']}")
            
    return asset_map

def seed_links(session, asset_map):
    print("Seeding Plan Links...")
    # standard plans
    plans = session.exec(select(Plan)).all()
    
    for plan in plans:
        # Standard or Family
        if "standard" in plan.slug or "family" in plan.slug:
            # Minimal Mode -> Shared Minimal
            ensure_link(session, plan.id, "minimal", asset_map.get("shared:minimal_system"), asset_map.get("shared:minimal_schema"))
            # Detailed Mode -> Shared Detailed + Canonical Schema
            ensure_link(session, plan.id, "detailed", asset_map.get("shared:detailed_system"), asset_map.get("shared:canonical_schema"))
            
        elif "free" in plan.slug:
            # Minimal Mode -> Free Assets (or shared minimal if free missing?)
            # Use free assets if available
            sys_id = asset_map.get("free:system") or asset_map.get("shared:minimal_system")
            sch_id = asset_map.get("free:schema") or asset_map.get("shared:minimal_schema")
            ensure_link(session, plan.id, "minimal", sys_id, sch_id)
            # Detailed Mode -> None (Free doesn't allow detailed) for now. Admin can enable later.

def ensure_link(session, plan_id, mode, sys_id, sch_id):
    if not sys_id or not sch_id:
        print(f"Skipping link for Plan {plan_id} {mode}: missing assets")
        return

    link = session.exec(select(PlanPromptLink).where(PlanPromptLink.plan_id == plan_id, PlanPromptLink.mode == mode)).first()
    if link:
        # Update just in case
        link.system_prompt_asset_id = sys_id
        link.schema_prompt_asset_id = sch_id
        session.add(link)
        print(f"Updated link: Plan {plan_id} Mode {mode}")
    else:
        link = PlanPromptLink(plan_id=plan_id, mode=mode, system_prompt_asset_id=sys_id, schema_prompt_asset_id=sch_id)
        session.add(link)
        print(f"Created link: Plan {plan_id} Mode {mode}")
    session.commit()

def main():
    print("Running migration/seed for PromptAssets...")
    # Create tables if not exist
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        asset_map = seed_assets(session)
        seed_links(session, asset_map)
    print("Done.")

if __name__ == "__main__":
    main()
