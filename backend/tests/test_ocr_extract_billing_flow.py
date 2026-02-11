import base64
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api import api_router
from app.database import get_session
from app.models import User, CreditLot, CreditHold, OCRJob, SystemConfig
from app.constants.token_policy_defaults import TOKEN_POLICY_DEFAULTS
import app.api as api_module

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABJACfWQAAAABJRU5ErkJggg=="
)

fastapi_app = FastAPI()
fastapi_app.include_router(api_router)


@pytest.fixture(name="session")
def session_fixture():
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


def _seed_token_policy_defaults(session: Session) -> None:
    for key, (value, description) in TOKEN_POLICY_DEFAULTS.items():
        session.add(SystemConfig(key=key, value=str(value), description=description))
    session.commit()


def _seed_user_with_credits(session: Session) -> User:
    user = User(email="ocr@test.com", full_name="OCR Test", password_hash="x")
    session.add(user)
    session.commit()
    lot = CreditLot(
        user_id=user.id,
        credits_total=20,
        credits_remaining=20,
        status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    session.add(lot)
    session.commit()
    session.refresh(user)
    return user


def test_ocr_extract_applies_hold_and_caches(client, session, monkeypatch):
    user = _seed_user_with_credits(session)

    async def fake_extract(*args, **kwargs):
        return {
            "payload": {
                "ok": True,
                "questions": [{"text": "Solve x+1=2"}],
            },
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
        }

    monkeypatch.setattr(api_module, "_call_extract_questions", fake_extract)

    files = {"file": ("test.png", PNG_BYTES, "image/png")}
    resp = client.post(f"/ocr/extract?user_id={user.id}", files=files, data={"engine": "pix2text"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["billing"]["hold_applied"] is True
    assert data["billing"]["hold_amount"] == 2.0
    assert data["cache_hit"] is False

    hold_count = len(session.exec(select(CreditHold)).all())
    assert hold_count == 1

    # Second call should hit cache and not create another hold
    resp2 = client.post(f"/ocr/extract?user_id={user.id}", files=files, data={"engine": "pix2text"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cache_hit"] is True

    hold_count2 = len(session.exec(select(CreditHold)).all())
    assert hold_count2 == 1


def test_ocr_extract_failure_releases_hold(client, session, monkeypatch):
    user = _seed_user_with_credits(session)

    async def fake_extract(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_module, "_call_extract_questions", fake_extract)

    files = {"file": ("test.png", PNG_BYTES, "image/png")}
    resp = client.post(f"/ocr/extract?user_id={user.id}", files=files, data={"engine": "pix2text"})
    assert resp.status_code == 502

    job = session.exec(select(OCRJob).order_by(OCRJob.created_at.desc())).first()
    assert job is not None

    hold = session.exec(select(CreditHold).order_by(CreditHold.created_at.desc())).first()
    assert hold is not None
    assert hold.status in {"released", "released_void", "failed"}


def test_ocr_extract_empty_payload_returns_no_content_and_releases_hold(client, session, monkeypatch):
    user = _seed_user_with_credits(session)

    async def fake_extract(*args, **kwargs):
        return {
            "payload": {
                "ok": True,
                "questions": [],
                "notes": ["No math questions detected."],
            },
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
        }

    monkeypatch.setattr(api_module, "_call_extract_questions", fake_extract)

    files = {"file": ("test.png", PNG_BYTES, "image/png")}
    resp = client.post(f"/ocr/extract?user_id={user.id}", files=files, data={"engine": "pix2text"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_content"
    assert (data.get("extracted_text") or "") == ""
    assert data["billing"]["hold_applied"] is False

    hold = session.exec(select(CreditHold).order_by(CreditHold.created_at.desc())).first()
    assert hold is not None
    assert hold.status in {"released", "released_void", "failed"}
