import asyncio
import os
import sys

# Ensure backend root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from app.database import engine
from app.models import PromptBinding, PromptTemplateEntry, JsonSchemaEntry, PromptTierEnum, PromptModeEnum

def update_bindings():
    print("Updating Local DB Bindings to match Production Expectations...")
    
    with Session(engine) as session:
        # 1. Update STANDARD User Bundle
        # Target: Mode=SOLVE, Tier=STANDARD -> Prompt=solve_standard_v1, Schema=...standard_detailed...
        
        # Check if Prompt exists
        prompt = session.exec(select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == "solve_standard_v1")).first()
        if not prompt:
            print("[WARN] 'solve_standard_v1' prompt not found in registry. Skipping.")
        else:
            print(f"[OK] Found prompt: {prompt.prompt_id}")

        # Find existing binding
        binding = session.exec(
            select(PromptBinding)
            .where(PromptBinding.mode == PromptModeEnum.SOLVE)
            .where(PromptBinding.tier == PromptTierEnum.STANDARD)
            .where(PromptBinding.is_active == True)
        ).first()

        if binding:
            print(f"Current STANDARD Binding: Prompt={binding.developer_prompt_id}, Schema={binding.output_schema_id}")
            if binding.developer_prompt_id != "solve_standard_v1":
                print(f"Updating STANDARD binding prompt to 'solve_standard_v1'")
                binding.developer_prompt_id = "solve_standard_v1"
                session.add(binding)
                session.commit()
                print("Updated.")
            else:
                print("STANDARD binding already correct.")
        else:
            print("[WARN] No active STANDARD binding found.")

        # 2. Update RESEARCH User Bundle (Same logic, usually uses standard or research prompt)
        binding_res = session.exec(
            select(PromptBinding)
            .where(PromptBinding.mode == PromptModeEnum.SOLVE)
            .where(PromptBinding.tier == PromptTierEnum.RESEARCH)
            .where(PromptBinding.is_active == True)
        ).first()

        if binding_res:
            print(f"Current RESEARCH Binding: Prompt={binding_res.developer_prompt_id}, Schema={binding_res.output_schema_id}")
            # Assuming research uses same standard prompt or specific one? 
            # If solve_research_v1 exists use it, otherwise solve_standard_v1
            target_prompt = "solve_standard_v1" # Fallback
            p_res = session.exec(select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == "solve_research_v1")).first()
            if p_res:
                target_prompt = "solve_research_v1"
            
            if binding_res.developer_prompt_id != target_prompt:
                print(f"Updating RESEARCH binding prompt to '{target_prompt}'")
                binding_res.developer_prompt_id = target_prompt
                session.add(binding_res)
                session.commit()
            else:
                 print("RESEARCH binding already correct.")

if __name__ == "__main__":
    update_bindings()
