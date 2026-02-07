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
from app.api import solve_problem, SolveRequest
from fastapi import Request
from sqlmodel import select
from unittest.mock import AsyncMock, patch
import uuid


async def verify_persistence():
    print("Verifying Persistence...")
    
    # 1. Setup Mock Request and dependency mocks
    req = MagicMock(spec=Request)
    req.headers = {"X-Request-ID": "test-trace-id-123"}
    
    body = SolveRequest(
        text_query="Test Question for Persistence",
        user_id=1,
        mode="debug"
    )
    
    # Mock Session (but use a real one for DB checking if possible, or just mock the add/commit)
    # To verifying REAL persistence, we need the real DB.
    # We will use `get_session` context manager if we can, or just creating one.
    
    # We'll use a mocked session for the API call to avoid side effects? 
    # NO, we want to see it in the DB.
    
    # But `solve_problem` takes a session.
    # We need to run `solve_problem` with a REAL session.
    # But we need to MOCK `solver.solve` to avoid OpenAI cost/latency.
    
    session_generator = get_session()
    session = next(session_generator)
    
    try:
        # Mock SolverV3
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
            mock_solver_instance = AsyncMock()
            mock_solver_instance.solve.return_value = {
                "problem": {"original_text": "Test Question", "normalized_text": "Test Question", "detected_tasks": []},
                "solution": {"final_answer": "42"},
                "_model": "mock-model"
            }
            mock_get_solver.return_value = mock_solver_instance
            
            # Mock RAG to avoid index lookup issues
            with patch("app.api.rag_service.search_related_concepts", new_callable=AsyncMock) as mock_rag:
                mock_rag.return_value = []
                
                # Mock Rate Limiter (Limiter is a decorator, might be tricky)
                # Decorators are applied at definition time. 
                # We are calling `solve_problem` directly as a function, so decorators *might* not enforce limits 
                # depending on how `limiter` works (SlowAPI uses decorators that return a wrapper).
                # If solve_problem is wrapped, we might hit rate limits or need mock request to have .state.
                
                # If `solve_problem` is decorated, `solve_problem` IS the wrapper.
                # We can try calling `solve_problem.__wrapped__` if it exists, or just ensure request has state.
                
                req.state = MagicMock()
                
                # 2. Call API
                print("Calling solve_problem...")
                try:
                    # We might need to mock `check_tokens` too if user has no tokens.
                    # Ensure user 1 exists.
                    user = session.get(User, 1)
                    if not user:
                        print("User 1 not found, creating dummy user.")
                        user = User(id=1, email="test@test.com", hashed_password="pw")
                        session.add(user)
                        session.commit()
                        
                    response = await solve_problem(req, body, session)
                    print("API returned success.")
                except Exception as e:
                    print(f"API failed (expected if mocking is incomplete, but let's check attempts): {e}")

        # 3. Verify DB
        print("Checking DB for attempts...")
        attempts = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.input_text_raw == "Test Question for Persistence")).all()
        
        if attempts:
            print(f"SUCCESS: Found {len(attempts)} attempts.")
            for att in attempts:
                print(f" - Attempt ID: {att.attempt_id}")
                print(f" - Input: {att.input_text_raw}")
                print(f" - Status: {att.status}")
                print(f" - Created At: {att.created_at}")
        else:
            print("FAILURE: No attempts found with matching input text.")

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(verify_persistence())
