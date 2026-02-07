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
from datetime import datetime
import time

from app.main import app
from app.api import get_session
from app.models import SolverOutputAttempt, User, SystemConfig, Plan, Subscription

client = TestClient(app)

@pytest.fixture(name="session")
def session_fixture():
    from app.database import engine
    from sqlmodel import SQLModel
    
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.merge(SystemConfig(key="text_input_max", value="4000"))
        session.commit()
        yield session

@pytest.fixture(name="user_fixture")
def user_fixture(session):
    email = f"ambiguity-{int(time.time())}-{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=email, 
        password_hash="hashed", 
        full_name="Ambiguity User",
        subscription_tier="free"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    from app.services.subscription_service import subscription_service
    subscription_service.get_or_create_subscription(session, user)
    
    plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
    if plan:
        feats = dict(plan.features)
        feats["daily_credit_cap"] = 1000000
        plan.features = feats
        session.add(plan)
        
    if user.subscription:
        user.subscription.credits_balance = 1000000.0
        session.add(user.subscription)
        
    session.commit()
    session.refresh(user)
    return user

def test_ambiguous_error_signaling(session, user_fixture):
    """Test that solve_v3_stream returns ambiguous_response error code"""
    with patch("app.api._validate_stream_payload") as mock_val:
        mock_val.return_value = ([], True)
        
        with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
            mock_solver_inst = MagicMock()
            mock_get_solver.return_value = mock_solver_inst
            
            async def mock_stream(*args, **kwargs):
                yield {"type": "delta", "text": '{"is_ambiguous": true, "refusal": "Clarification please"}'}
                yield {"type": "telemetry", "telemetry": {"total_tokens": 10, "latency_ms_total": 100}}
            
            mock_solver_inst.solve_stream = mock_stream
            
            response = client.post(
                f"/api/v1/solve_v3_stream?user_id={user_fixture.id}",
                json={
                    "confirmed_text": "Solve x",
                    "requested_mode": "minimal",
                    "tier": "free",
                    "features_used": {}
                }
            )
            
            assert response.status_code == 200
            events = response.text.split("\n\n")
            data = None
            for e in events:
                if "event: done" in e:
                    line = e.split("data: ")[1]
                    data = json.loads(line)
                    break
            
            if not data:
                data_lines = [e for e in events if "data: {" in e]
                data = json.loads(data_lines[-1].split("data: ")[1])
            
            assert data["ok"] is False
            assert "ambiguous_response" in str(data)

def test_clarify_endpoint_success(session, user_fixture):
    """Test the /api/v1/solve/clarify endpoint"""
    attempt_id = "test-att-" + str(uuid.uuid4())
    from app.models import ChatSession
    chat_session = ChatSession(user_id=user_fixture.id, title="Test Session")
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)

    attempt = SolverOutputAttempt(
        request_id=attempt_id,
        attempt_id=attempt_id,
        user_id=user_fixture.id,
        status="ambiguous",
        input_text_raw="Solve x",
        created_at=datetime.utcnow(),
        session_id=chat_session.id
    )
    session.add(attempt)
    session.commit()
    
    with patch("app.services.solver_v3.get_solver_v3") as mock_get_solver:
        mock_solver_inst = MagicMock()
        mock_get_solver.return_value = mock_solver_inst
        
        async def mock_solve(*args, **kwargs):
            db_session = kwargs.get('db_session')
            attempt_id = kwargs.get('attempt_id')
            if db_session and attempt_id:
                from app.models import SolverOutputAttempt
                att = db_session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
                if att:
                    att.status = "success"
                    db_session.add(att)
                    db_session.commit()

            return {
                "steps": [{"title": "S1", "explanation": "E1", "math_latex": "x=1"}],
                "final_answer": {"answer_text": "1", "answer_latex": "1"},
                "meta": {"tokens": 10, "model": "test-model"}
            }
        mock_solver_inst.solve = mock_solve
        
        response = client.post(
            "/api/v1/solve/clarify",
            json={"attempt_id": attempt_id, "user_response": "x is 1"}
        )
        
        if response.status_code != 200:
            print(f"DEBUG: Body={response.text}")
            
        assert response.status_code == 200
        data = response.json()
        assert "solution" in data
        assert data["session_id"] == chat_session.id
        
        session.refresh(attempt)
        assert attempt.status == "success"
        assert attempt.clarification_count == 1
