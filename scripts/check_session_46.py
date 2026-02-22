import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.database import engine
from sqlmodel import Session, select
from app.models import ChatSession, ChatMessage, SolverOutputAttempt, PromptBinding

def main():
    with Session(engine) as session:
        cs = session.get(ChatSession, 46)
        if not cs:
            print("Session 46 not found.")
            # Let's see if 46 exists at all or if there are others
            all_sessions = session.exec(select(ChatSession).order_by(ChatSession.id.desc()).limit(5)).all()
            print("Recent sessions in DB:")
            for s in all_sessions:
                print(f"  ID: {s.id}, Title: {s.title}, Created: {s.created_at}")
            return
            
        print(f"Session ID: {cs.id}, Created At: {cs.created_at}")
        
        # Check attempts linked to this session
        attempts = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.session_id == 46).order_by(SolverOutputAttempt.created_at)).all()
        print(f"Attempts linked to session 46: {len(attempts)}")
        
        for att in attempts:
            print(f"--- Attempt ID: {att.id} (UUID: {att.attempt_id}) ---")
            print(f"  Status: {att.status}")
            print(f"  Provider: {att.provider}")
            print(f"  Model: {att.model}")
            print(f"  Created At: {att.created_at}")
            print(f"  Prompt Meta: {att.prompt_meta}")
            
            if att.prompt_meta and 'binding_id' in att.prompt_meta:
                binding_id = att.prompt_meta['binding_id']
                binding = session.get(PromptBinding, binding_id)
                if binding:
                    print(f"  Binding in DB for {binding_id}:")
                    print(f"    Tier: {binding.tier}")
                    print(f"    Provider: {binding.provider}")
                    print(f"    Active: {binding.is_active}")
            
            if att.status == 'failure' or att.failure_code:
                print(f"  Failure Code: {att.failure_code}")
                print(f"  Error Message: {att.error_message}")

if __name__ == "__main__":
    main()
