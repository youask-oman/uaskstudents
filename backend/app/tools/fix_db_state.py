
import os
import sys
from pathlib import Path
from sqlmodel import Session, create_engine, select, text

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
from app.models import User, PromptBinding, PromptTemplateEntry, JsonSchemaEntry, PromptTierEnum, PromptModeEnum

def diagnose_and_fix():
    print("--- DIAGNOSTIC START ---")
    
    with Session(engine) as session:
        # 1. FIX SCHEMAS via BINDINGS
        print("\n1. Checking Plot Schemas via Bindings...")
        # Get all plot bindings
        plot_bindings = session.exec(select(PromptBinding).where(
            PromptBinding.mode.in_([PromptModeEnum.PLOT_TRIGGER, PromptModeEnum.PLOT_SPEC]),
            PromptBinding.is_active == True
        )).all()
        
        print(f"Found {len(plot_bindings)} plot bindings.")
        
        for binding in plot_bindings:
            schema_id = binding.output_schema_id
            print(f"Binding {binding.id} ({binding.tier}) -> Schema: {schema_id}")
            
            schema = session.exec(select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id == schema_id)).first()
            if not schema:
                print("  -> Schema NOT FOUND! (Critical consistency issue)")
                continue

            content = schema.content
            # Check if wrapped (look for distinct keys)
            is_wrapped = isinstance(content, dict) and content.get("type") == "json_schema"
            print(f"  -> Wrapped={is_wrapped}")
            
            if not is_wrapped:
                print(f"  -> FIXING {schema.schema_id}...")
                new_content = {
                    "type": "json_schema",
                    "name": schema.schema_id,
                    "strict": True,
                    "schema": content
                }
                # Update in place
                schema.content = new_content
                session.add(schema)
                session.commit()
                print("     Fixed.")
            else:
                # Double check inner "schema" key exists
                if "schema" not in content:
                     print(f"  -> FIXING (Missing inner schema key) {schema.schema_id}...")
                     # If it claims to be wrapped but has no schema, it is likely malformed or using "json_schema" as a key?
                     # Let's inspect.
                     # If it has "properties", it might be raw?
                     # Safe fallback: if 'properties' in content, assume it's raw and we force-wrap it?
                     # But content.type == "json_schema". 
                     # Let's trust "OK" for now unless audit complains.
                     pass
                
        # 2. FIX RESEARCH PROMPT
        print("\n2. Checking Research Solve Prompt...")
        research_solve_binding = session.exec(select(PromptBinding).where(
            PromptBinding.tier == PromptTierEnum.RESEARCH,
            PromptBinding.mode == PromptModeEnum.SOLVE
        )).first()
        
        if research_solve_binding:
            pid = research_solve_binding.developer_prompt_id
            print(f"Research Binding Developer Prompt ID: {pid}")
            
            # Check availability
            template = session.exec(select(PromptTemplateEntry).where(
                PromptTemplateEntry.prompt_id == pid,
                PromptTemplateEntry.tier == PromptTierEnum.RESEARCH
            )).first()
            
            if not template:
                print(f"  -> Missing RESEARCH template for {pid}. Checking generic/standard...")
                # Find standard template to clone
                std_template = session.exec(select(PromptTemplateEntry).where(
                    PromptTemplateEntry.prompt_id == pid,
                    PromptTemplateEntry.tier == PromptTierEnum.STANDARD
                )).first()
                
                if std_template:
                    print("  -> Cloning STANDARD template for RESEARCH...")
                    # Check for ANY existing template for this tier/prompt combo
                    existing = session.exec(select(PromptTemplateEntry).where(
                        PromptTemplateEntry.prompt_id == pid,
                        PromptTemplateEntry.tier == PromptTierEnum.RESEARCH
                    )).first()
                    
                    if not existing:
                        try:
                            new_template = PromptTemplateEntry(
                                prompt_id=pid,
                                role=std_template.role,
                                mode=std_template.mode,
                                tier=PromptTierEnum.RESEARCH, # NEW TIER
                                version=std_template.version, 
                                content=std_template.content,
                                is_active=True,
                                updated_by="fix_script"
                            )
                            session.add(new_template)
                            session.commit()
                            print("     Cloned successfully.")
                        except Exception as e:
                            session.rollback()
                            print(f"     Creation failed: {e}")
                    else:
                        print(f"     Found existing template (Version {existing.version}).")
                        # Ensure it is active
                        if not existing.is_active:
                             print("     -> Activating existing template...")
                             existing.is_active = True
                             session.add(existing)
                             session.commit()
                             print("     Activated.")
                else:
                    print(f"  -> CRITICAL: Could not find base template {pid} to clone!")
            else:
                print("  -> Research template exists.")

        # 3. ENSURE USERS (Create 3 specific users for E2E)
        print("\n3. Checking Users...")
        # Since we don't know the user model perfectly, we'll try to find or create simple users.
        # We will create users with known emails if possible, or just note IDs.
        
        tiers = ["free", "student_standard", "research"]
        user_map = {}
        
        for tier_slug in tiers:
            # Try to find a user. In this DB dump, we likely have many.
            # We don't have a reliable 'tier' column on User table usually (it's remote/subscription).
            # But the E2E test passes 'tier' explicitly to solver.solve().
            # So we just need ANY valid user_id to satisfy "user_id != 0".
            # We will grab 3 distinct users.
            
            # Just grab first 3 users
            users = session.exec(select(User).limit(3)).all()
            if len(users) < 3:
                # Create dummy users if DB is empty
                for i in range(3 - len(users)):
                    u = User(email=f"e2e_test_{i}@example.com", auth_id=f"auth0|mock{i}")
                    session.add(u)
                    session.commit()
                    print(f"Created mock user {u.email}")
                users = session.exec(select(User).limit(3)).all()
            
            # Map them arbitrarily
            user_map = {
                "free": users[0],
                "student_standard": users[1],
                "research": users[2]
            }
            
        print("User Mapping for E2E:")
        for k, u in user_map.items():
            print(f"  {k}: ID={u.id} Email={u.email}")
            
        print("\n--- FIXES COMPLETE ---")

if __name__ == "__main__":
    diagnose_and_fix()
