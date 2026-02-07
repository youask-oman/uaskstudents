import asyncio
import uuid
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_session
from app.models import SolverOutputAttempt, User
from sqlmodel import select
from datetime import datetime

def verify_db_schema():
    print("Verifying DB Schema for SolverOutputAttempt...")
    
    session_generator = get_session()
    session = next(session_generator)
    
    try:
        # 1. Create User
        user = session.get(User, 1)
        if not user:
            user = User(id=1, email="test_simple@test.com", hashed_password="pw")
            session.add(user)
            session.commit()
            
        # 2. Create Attempt
        uid = str(uuid.uuid4())
        print(f"Creating attempt {uid}...")
        attempt = SolverOutputAttempt(
            request_id="req-simple",
            attempt_id=uid,
            user_id=1,
            status="pending",
            input_text_raw="Simple Test",
            prompt_meta={"ver": "1.0"},
            llm_raw_response={"foo": "bar"},
            validation_errors=[{"err": "1"}],
            clarification_count=0,
            clarification_history=[],
            created_at=datetime.utcnow()
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        
        # 3. Read Attempt
        read_att = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == uid)).first()
        if read_att:
            print(f"SUCCESS: Read back attempt {read_att.attempt_id}")
            print(f"Status: {read_att.status}")
            print(f"Input: {read_att.input_text_raw}")
            print(f"Meta: {read_att.prompt_meta}")
            print(f"Validation Errors: {read_att.validation_errors}")
        else:
            print("FAILURE: Could not read back attempt.")
            
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    verify_db_schema()
