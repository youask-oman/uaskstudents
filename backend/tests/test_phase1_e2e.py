import sys
from unittest.mock import MagicMock

# MOCK HEAVY ML DEPENDENCIES to avoid environment issues during E2E proof
sys.modules["torch"] = MagicMock()
sys.modules["torch.version"] = MagicMock()
sys.modules["torch.__version__"] = "2.0.0"
sys.modules["pix2text"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from unittest.mock import patch, MagicMock
import json
import uuid

from app.api import app, get_session
from app.models import SolverOutputAttempt, User, SystemConfig
from app.services.solver_v3 import SolverV3

client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    from app.database import engine
    from sqlmodel import SQLModel
    
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed SystemConfig for token limits
        session.add(SystemConfig(key="text_input_max", value="4000"))
        session.add(SystemConfig(key="ocr_image_input_max", value="4000"))
        session.add(SystemConfig(key="voice_input_max", value="4000"))
        session.commit()
        yield session

@pytest.fixture(name="user_fixture")
def user_fixture(session):
    user = User(
        email=f"e2e_{uuid.uuid4()}@test.com", 
        hashed_password="hashed", 
        full_name="E2E User",
        password_hash="hashed"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# Mock the solver to avoid real OpenAI calls
# Mock the solver to avoid real OpenAI calls
@pytest.fixture
def mock_solver():
    import app.services.solver_v3 as solver_module
    print(f"DEBUG: solver_module={solver_module}")
    with patch.object(solver_module, "get_solver_v3") as mock_get:
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance
        yield mock_instance

def test_e2e_01_success_solve(session, user_fixture, mock_solver):
    """E2E-01: Standard success flow"""
    # Mock successful response
    mock_solver.solve.return_value = {
        "solution": {"final_answer": "42", "steps": []},
        "_model": "gpt-4-mock",
        "_telemetry": {"total_tokens": 100, "latency_ms_total": 500}
    }
    
    response = client.post(
        "/api/v1/solve",
        json={"text_query": "What is 6*7?", "user_id": user_fixture.id}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["solution"]["final_answer"] == "42"
    
    # Verify DB persistence
    attempt = session.exec(select(SolverOutputAttempt).order_by(SolverOutputAttempt.created_at.desc())).first()
    assert attempt.status == "success"
    assert attempt.input_text_raw == "What is 6*7?"
    assert attempt.attempt_id is not None

def test_e2e_02_clarification_flow(session, user_fixture, mock_solver):
    """E2E-02 & E2E-03: Clarification loop"""
    # 1. Initial Ambiguous Request
    # We simulate this by having the solver return specific data or by checking the logic that throws AmbiguousRequestError
    # But since logic is inside solver.solve, we mock it to return 'ambiguous' status if we can?
    # Actually, solver.solve raises AmbiguousRequestError or returns it?
    # The implementation plan says handle AmbiguousRequestError.
    # Let's assume solver.solve works and returns {status: ambiguous...} or raises exception.
    # The current code in api.py doesn't show explicit catch for AmbiguousRequestError, 
    # but `solve_clarify` exists.
    # Let's Manually CREATE an ambiguous attempt since mocking the internal exception flow is checking implementation details.
    
    attempt_id = str(uuid.uuid4())
    attempt = SolverOutputAttempt(
        request_id="req-123",
        attempt_id=attempt_id,
        user_id=user_fixture.id,
        status="ambiguous", # Pre-set to ambiguous
        error_message="Do you mean x or y?",
        input_text_raw="Solve x",
        clarification_count=0
    )
    session.add(attempt)
    session.commit()
    
    # 2. Clarify #1
    mock_solver.solve.return_value = {
        "solution": {"final_answer": "x=5"},
        "_model": "gpt-4-mock"
    }
    
    response = client.post(
        "/api/v1/solve/clarify",
        json={"attempt_id": attempt_id, "user_response": "I mean x"}
    )
    
    assert response.status_code == 200
    
    session.refresh(attempt)
    assert attempt.clarification_count == 1
    assert attempt.clarification_history[0]["answer"] == "I mean x"
    assert attempt.status == "success" # Mock returned success

def test_e2e_04_exceed_cap(session, user_fixture):
    """E2E-04: Exceed clarification cap"""
    attempt_id = str(uuid.uuid4())
    attempt = SolverOutputAttempt(
        request_id="req-cap",
        attempt_id=attempt_id,
        user_id=user_fixture.id,
        status="ambiguous",
        clarification_count=2, # Limit reached
        input_text_raw="Solve x"
    )
    session.add(attempt)
    session.commit()
    
    response = client.post(
        "/api/v1/solve/clarify",
        json={"attempt_id": attempt_id, "user_response": "One more time"}
    )
    
    assert response.status_code == 400
    assert "Max clarifications reached" in response.json()["detail"]
    
    session.refresh(attempt)
    assert attempt.status == "failure"
    assert attempt.failure_code == "AMBIGUOUS_AFTER_CLARIFICATIONS"

def test_e2e_07_resume_state(session, user_fixture):
    """E2E-07: Get Attempt Status"""
    attempt_id = str(uuid.uuid4())
    attempt = SolverOutputAttempt(
        request_id="req-resume",
        attempt_id=attempt_id,
        user_id=user_fixture.id,
        status="ambiguous",
        error_message="Clarify please",
        clarification_count=1
    )
    session.add(attempt)
    session.commit()
    
    response = client.get(f"/api/v1/attempt/{attempt_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ambiguous"
    assert data["clarification_count"] == 1
    assert data["error_message"] == "Clarify please"

