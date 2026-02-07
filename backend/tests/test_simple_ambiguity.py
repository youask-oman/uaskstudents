import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
import uuid

# MOCK HEAVY ML DEPENDENCIES
import sys
sys.modules["torch"] = MagicMock()
sys.modules["torch.version"] = MagicMock()
sys.modules["torch.__version__"] = "2.0.0"
sys.modules["pix2text"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

from app.main import app
from app.api import get_session
from app.models import SolverOutputAttempt, User, SystemConfig
from sqlmodel import Session, select

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
    user = session.exec(select(User).where(User.email == "test@test.com")).first()
    if not user:
        user = User(email="test@test.com", hashed_password="hashed", full_name="Test User", password_hash="hashed")
        session.add(user)
        session.commit()
        session.refresh(user)
    return user

def test_simplest_stream(session, user_fixture):
    # Just test if the endpoint returns SOMETHING without crashing
    # We gotta mock the solver though because it calls the real LLM
    with patch("app.services.solver_v3.get_solver_v3") as mock_get:
        mock_solver = MagicMock()
        mock_get.return_value = mock_solver
        
        async def mock_solve_stream(*args, **kwargs):
            yield {"type": "delta", "text": "Hello"}
            yield {"type": "telemetry", "telemetry": {"total_tokens": 5}}

        mock_solver.solve_stream = mock_solve_stream
        
        response = client.post(
            f"/api/v1/solve_v3_stream?user_id={user_fixture.id}",
            json={
                "confirmed_text": "Calculate 1+1",
                "requested_mode": "minimal",
                "tier": "free",
                "features_used": {}
            }
        )
        assert response.status_code == 200
        assert "event: delta" in response.text
