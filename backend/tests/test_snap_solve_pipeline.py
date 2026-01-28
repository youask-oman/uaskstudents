import base64
import pytest
from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api import api_router
from app.constants.token_policy_defaults import TOKEN_POLICY_DEFAULTS
from app.database import get_session
from app.models import SystemConfig, User
import app.api as api_module

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABJACfWQAAAABJRU5ErkJggg=="
)

fastapi_app = FastAPI()
fastapi_app.include_router(api_router)


@pytest.fixture(name="session")
def session_fixture():
    from sqlmodel.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_token_policy_defaults(session)
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session
    fastapi_app.dependency_overrides[get_session] = get_session_override
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()


def test_extract_questions_caches(client, session, monkeypatch):
    user = User(email="snap@test.com", full_name="Snap Test", password_hash="x")
    session.add(user)
    session.commit()

    async def fake_extract(_bytes, _max_output_tokens):
        return {
            "payload": {
                "is_math_page": True,
                "notes": [],
                "questions": [
                    {
                        "id": "q1",
                        "text": "Solve x+1=2",
                        "confidence": 0.9,
                        "is_valid_math": True
                    }
                ]
            },
            "input_tokens": 10,
            "output_tokens": 20,
            "cached_tokens": 0
        }

    monkeypatch.setattr(api_module, "_call_extract_questions", fake_extract)

    files = {"file": ("test.png", PNG_BYTES, "image/png")}
    resp1 = client.post(
        f"/extract_questions?user_id={user.id}",
        files=files,
        data={"page_number": 1, "source": "image", "user_selection": "crop"}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["ok"] is True
    assert data1["cache_hit"] is False

    resp2 = client.post(
        f"/extract_questions?user_id={user.id}",
        files=files,
        data={"page_number": 1, "source": "image", "user_selection": "crop"}
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cache_hit"] is True


def test_solve_questions_batch_basic(client, session, monkeypatch):
    user = User(email="solve@test.com", full_name="Solve Test", password_hash="x")
    session.add(user)
    session.commit()

    class DummySolver:
        async def solve(self, **kwargs):
            return {
                "final_answer": {"answer_text": "x=1"},
                "telemetry": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            }

    import app.services.solver_v3 as solver_module
    monkeypatch.setattr(solver_module, "get_solver_v3", lambda: DummySolver())

    payload = {
        "items": [
            {"question_id": "q1", "text": "Solve x+1=2", "requested_mode": "minimal"}
        ],
        "features_used": {"ocr_used": True}
    }

    resp = client.post(f"/solve_questions_batch?user_id={user.id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["results"][0]["ok"] is True


def _seed_token_policy_defaults(session: Session) -> None:
    for key, (value, description) in TOKEN_POLICY_DEFAULTS.items():
        session.add(SystemConfig(key=key, value=str(value), description=description))
    session.commit()
