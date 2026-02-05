
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
from app.models import PromptTemplateEntry, PromptBinding, PromptTierEnum, PromptModeEnum

def fix_research_binding():
    with Session(engine) as session:
        print("--- FIX BINDING START ---")
        
        # 1. Get Research Binding
        binding = session.exec(select(PromptBinding).where(
            PromptBinding.tier == PromptTierEnum.RESEARCH,
            PromptBinding.mode == PromptModeEnum.SOLVE
        )).first()
        
        if not binding:
            print("CRITICAL: Research binding not found!")
            return

        print(f"Current Research Binding Dev Prompt ID: {binding.developer_prompt_id}")
        
        if binding.developer_prompt_id == "solve_standard_v1":
            print("-> Detected incorrect pointer to STANDARD prompt.")
            
            # 2. Check/Create 'solve_research_v1' template
            target_pid = "solve_research_v1"
            
            existing_tmpl = session.exec(select(PromptTemplateEntry).where(
                PromptTemplateEntry.prompt_id == target_pid,
                PromptTemplateEntry.tier == PromptTierEnum.RESEARCH
            )).first()
            
            if existing_tmpl:
                print(f"-> Target template {target_pid} already exists.")
            else:
                print(f"-> Creating {target_pid} by cloning solve_standard_v1...")
                # Get standard source
                std_tmpl = session.exec(select(PromptTemplateEntry).where(
                    PromptTemplateEntry.prompt_id == "solve_standard_v1",
                    PromptTemplateEntry.tier == PromptTierEnum.STANDARD
                )).first()
                
                if not std_tmpl:
                    print("CRITICAL: Source standard prompt not found!")
                    return
                
                new_tmpl = PromptTemplateEntry(
                    prompt_id=target_pid,
                    tier=PromptTierEnum.RESEARCH,
                    mode=std_tmpl.mode,
                    role=std_tmpl.role,
                    content=std_tmpl.content,
                    version=1,
                    is_active=True,
                    updated_by="fix_script"
                )
                session.add(new_tmpl)
                session.commit()
                print("-> Template created.")
                
            # 3. Update Binding
            print(f"-> Updating binding to point to {target_pid}...")
            binding.developer_prompt_id = target_pid
            session.add(binding)
            session.commit()
            print("-> Binding updated.")
            
        else:
            print(f"-> Binding already points to {binding.developer_prompt_id}. No action needed if correct.")
            
        print("--- FIX DONE ---")

if __name__ == "__main__":
    fix_research_binding()
