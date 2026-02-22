
import sys
import os
import json
# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.llm.manager import get_llm_manager
from app.database import engine
from sqlmodel import Session, select
from app.models import SystemConfig, PromptBinding

def verify():
    print("--- LLM Manager Verification ---")
    mgr = get_llm_manager()
    
    # Check if primary_provider attribute is gone (should be handled by get_active_provider)
    if hasattr(mgr, "primary_provider"):
        print("[FAIL] LLMManager still has 'primary_provider' attribute!")
    else:
        print("[OK] 'primary_provider' attribute removed.")

    # Check dynamic provider selection
    with Session(engine) as session:
        # Get active provider from DB
        active = mgr.get_active_provider(session)
        print(f"Active provider from DB (or fallback): {active}")
        
        # Test SystemConfig override
        print("Ensuring SystemConfig exists...")
        config = session.get(SystemConfig, "active_llm_provider")
        if not config:
            print("Creating default SystemConfig 'active_llm_provider' = 'openai'")
            config = SystemConfig(key="active_llm_provider", value="openai")
            session.add(config)
            session.commit()
            session.refresh(config)
        
        print(f"Current SystemConfig value: {config.value}")
        
        # Test switching
        old_val = config.value
        new_val = "ollama" if old_val == "openai" else "openai"
        print(f"Switching provider to: {new_val}")
        config.value = new_val
        session.add(config)
        session.commit()
        
        active_after = mgr.get_active_provider(session)
        print(f"Active provider after switch: {active_after}")
        
        if active_after == new_val:
            print("[OK] Dynamic switching working.")
        else:
            print("[FAIL] Dynamic switching failed.")
            
        # Revert
        config.value = old_val
        session.add(config)
        session.commit()
        print(f"Reverted provider to: {old_val}")

    print("\n--- PromptBinding Schema Verification ---")
    with Session(engine) as session:
        bindings = session.exec(select(PromptBinding).limit(1)).all()
        if bindings:
            b = bindings[0]
            if hasattr(b, "provider"):
                print(f"[OK] PromptBinding has 'provider' field: {b.provider}")
            else:
                print("[FAIL] PromptBinding MISSING 'provider' field!")
        else:
            print("[INFO] No PromptBindings found to check.")

    print("\n--- User Verification ---")
    with Session(engine) as session:
        from app.models import User
        user = session.get(User, 1)
        if user:
            print(f"[OK] Found user ID 1: {user.email}")
        else:
            print("[FAIL] User ID 1 NOT found! E2E test might fail if it relies on this ID.")
            # Check for any user
            any_user = session.exec(select(User).limit(1)).first()
            if any_user:
                print(f"[INFO] Found another user: ID={any_user.id}, email={any_user.email}")
            else:
                print("[FAIL] No users found in database.")

if __name__ == "__main__":
    verify()
