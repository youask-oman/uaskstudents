import asyncio
import uuid
import os
import sys

import sys
from unittest.mock import MagicMock

import sys
from unittest.mock import MagicMock

# Mock heavy/missing dependencies before API import
# Do NOT mock the parent 'app.services.ocr' as it breaks submodule resolution
sys.modules["app.services.ocr.ocr_service"] = MagicMock()
sys.modules["app.services.ocr.upload_service"] = MagicMock()
sys.modules["app.services.ocr.crop_service"] = MagicMock()
sys.modules["app.services.ocr.ocr_router_service"] = MagicMock()
sys.modules["app.services.ocr.audit_log_service"] = MagicMock()
sys.modules["app.services.ocr.vision_routing"] = MagicMock()
sys.modules["app.services.ocr.block_parser"] = MagicMock()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_session
from app.models import SolverOutputAttempt, User
from app.api import solve_clarify
from fastapi import Request
from sqlmodel import select
from datetime import datetime
from unittest.mock import AsyncMock, patch


async def verify_clarification():
    print("Verifying Clarification Logic...")
    
    # Setup Session
    session_generator = get_session()
    session = next(session_generator)
    
    # 1. Ensure an 'ambiguous' attempt exists
    attempt_id = str(uuid.uuid4())
    print(f"Creating ambiguous attempt: {attempt_id}")
    
    # Create user if needed
    user = session.get(User, 1)
    if not user:
        user = User(id=1, email="test@test.com", hashed_password="pw")
        session.add(user)
        session.commit()
    
    att = SolverOutputAttempt(
        request_id="test-clarify-req",
        attempt_id=attempt_id,
        user_id=1,
        status="ambiguous",
        input_text_raw="Ambiguous Question",
        created_at=datetime.utcnow(),
        error_message="Please clarify X or Y?"
    )
    session.add(att)
    session.commit()
    
    # 2. Call clarify endpoint
    print("Calling /solve/clarify...")
    
    req = MagicMock(spec=Request)
    
    # We mock solver to return success on clarification
    with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver: # Corrected patch path
        # solve_clarify uses `from app.services.solver_v3 import get_solver_v3` inside function.
        # mocking `app.services.solver_v3` module should work if we patch where it is used.
        # Since it is a local import inside function, we need to patch `app.services.solver_v3.get_solver_v3`?
        # Or `sys.modules['app.services.solver_v3'].get_solver_v3`?
        # `patch("app.services.solver_v3.get_solver_v3")` targets the module.
        
        # But wait, `solve_clarify` does `from app.services.solver_v3 import get_solver_v3`.
        # So we patch `app.services.solver_v3.get_solver_v3`.
        
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver_func:
            mock_solver = AsyncMock()
            mock_solver.solve.return_value = {
                "solution": {"final_answer": "Clarified 42"},
                "_model": "mock-clarify"
            }
            mock_get_solver_func.return_value = mock_solver
            
            try:
                # Call endpoint function directly
                # It takes (request, attempt_id, user_response, session)
                # But it uses Body(embed=True). Calling python function ignores Fastapi deps?
                # Yes, standard python call passes args directly.
                
                resp = await solve_clarify(
                    request=req,
                    attempt_id=attempt_id,
                    user_response="I mean X",
                    session=session
                )
                print("Clarification call success.")
                
                # Check DB update
                session.refresh(att)
                print(f"Attempt Status: {att.status}")
                print(f"Clarification Count: {att.clarification_count}")
                print(f"History: {att.clarification_history}")
                
                if att.clarification_count == 1 and len(att.clarification_history) == 1:
                    print("SUCCESS: Clarification history updated.")
                else:
                    print("FAILURE: History not updated correctly.")
                    
                # 3. Test Cap (Max 2)
                # Add another to reach 2
                att.clarification_count = 2
                session.add(att)
                session.commit()
                
                print("Testing Cap (should fail)...")
                try:
                    await solve_clarify(req, attempt_id, "More clarify", session)
                    print("FAILURE: Should have raised 400.")
                except Exception as e:
                    print(f"SUCCESS: Caught expected error: {e}")

            except Exception as e:
                print(f"Test Failed: {e}")
                import traceback
                traceback.print_exc()

    session.close()

if __name__ == "__main__":
    asyncio.run(verify_clarification())
