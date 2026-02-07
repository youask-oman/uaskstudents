import sys
from unittest.mock import MagicMock

# MOCK HEAVY ML DEPENDENCIES
sys.modules["torch"] = MagicMock()
sys.modules["torch.version"] = MagicMock()
sys.modules["torch.__version__"] = "2.0.0"
sys.modules["pix2text"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from unittest.mock import patch
import json
import uuid

from app.main import app
from app.api import get_session
from app.models import SolverOutputAttempt, User, SystemConfig

client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    from app.database import engine
    from sqlmodel import SQLModel
    
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed SystemConfig with merge to avoid IntegrityError
        session.merge(SystemConfig(key="text_input_max", value="4000"))
        session.commit()
        yield session

@pytest.fixture(name="user_fixture")
def user_fixture(session):
    user = session.exec(select(User).where(User.email.like("ambiguity_%"))).first()
    if not user:
        user = User(
            email=f"ambiguity_{uuid.uuid4()}@test.com", 
            hashed_password="hashed", 
            full_name="Ambiguity User",
            password_hash="hashed"
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user

def test_ambiguous_error_signaling(session, user_fixture):
    """Test that solve_v3_stream returns ambiguous_response error code"""
    # Mock _validate_stream_payload to return is_ambiguous=True
    # We patch it where it is used (app.api)
    with patch("app.api._validate_stream_payload") as mock_val:
        mock_val.return_value = ([], True) # no errors, but is_ambiguous
        
        # Patch get_solver_v3 in the service module since it's imported locally in api.py
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
            mock_solver_inst = MagicMock()
            mock_get_solver.return_value = mock_solver_inst
            
            async def mock_stream(*args, **kwargs):
                yield {"type": "delta", "text": '{"is_ambiguous": true, "refusal": "Please clarify"}'}
                yield {"type": "telemetry", "telemetry": {"total_tokens": 10, "latency_ms_total": 100}}
            
            mock_solver_inst.solve_stream = mock_stream
            
            response = client.post(
                f"/api/v1/solve_v3_stream?user_id={user_fixture.id}",
                json={
                    "confirmed_text": "Solve x",
                    "requested_mode": "detailed",
                    "tier": "free",
                    "features_used": {}
                }
            )
            
            assert response.status_code == 200
            events = response.text.split("\n\n")
            done_event = [e for e in events if "event: done" in e][0]
            data = json.loads(done_event.split("data: ")[1])
            
            assert data["ok"] is False
            assert data["error"]["code"] == "ambiguous_response"

def test_clarify_endpoint_success(session, user_fixture):
    """Test the /api/v1/solve/clarify endpoint"""
    attempt_id = str(uuid.uuid4())
    attempt = SolverOutputAttempt(
        request_id="req-clarify-1",
        attempt_id=attempt_id,
        user_id=user_fixture.id,
        status="ambiguous",
        input_text_raw="Solve x",
        clarification_count=0
    )
    session.add(attempt)
    session.commit()
    
    with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
        mock_solver_inst = MagicMock()
        mock_get_solver.return_value = mock_solver_inst
        
        # Mocking solver.solve to return a result that can be transformed by _transform_v3_to_v1_format
        mock_solver_inst.solve.return_value = {
            "steps": [
                {
                    "title": "Step 1",
                    "explanation": "Test explanation",
                    "math_latex": "x = 42"
                }
            ],
            "final_answer": {
                "answer_text": "The answer is 42",
                "answer_latex": "42"
            },
            "meta": {"tokens": 50}
        }
        
        response = client.post(
            "/api/v1/solve/clarify",
            json={
                "attempt_id": attempt_id,
                "user_response": "I mean x=42"
            }
        )
        
        # If still 500, we'll see it in the status check
        assert response.status_code == 200
        data = response.json()
        assert "solution" in data or "steps" in data # V1 has steps at top level after transform
        
        session.refresh(attempt)
        assert attempt.status == "success"
        assert attempt.clarification_count == 1
