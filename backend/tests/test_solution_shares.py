from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api import api_router
from app.auth import get_password_hash
from app.database import get_session
from app.models import ChatMessage, ChatSession, SolutionShare, SolverOutputAttempt, User


def _build_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    return app, engine


def _create_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        full_name="Share Test User",
        password_hash=get_password_hash("password123"),
        role="student",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_header(client: TestClient, email: str, password: str = "password123") -> dict:
    login = client.post("/api/v1/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_attempt(session: Session, owner_user_id: int, *, with_private_fields: bool = True) -> SolverOutputAttempt:
    chat = ChatSession(
        user_id=owner_user_id,
        title="Shareable Session",
        subject="Math",
        is_saved=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    structured = {
        "problem": {"original_text": "Solve x^2 - 5x + 6 = 0", "user_id": owner_user_id},
        "solution": {
            "steps": [{"title": "Factor", "explanation": "x^2 - 5x + 6 = (x-2)(x-3)"}],
            "final_answer": {"answer_latex": "x=2,3"},
        },
        "telemetry": {"request_id": "req-1", "provider": "openai", "total_tokens": 321},
    }
    if not with_private_fields:
        structured.pop("telemetry", None)

    message = ChatMessage(
        session_id=int(chat.id or 0),
        role="assistant",
        content="structured",
        structured_data=structured,
        created_at=datetime.utcnow(),
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    attempt = SolverOutputAttempt(
        request_id=f"req-{uuid.uuid4()}",
        attempt_id=str(uuid.uuid4()),
        user_id=owner_user_id,
        session_id=int(chat.id or 0),
        message_id=int(message.id or 0),
        output_format="json_schema",
        attempt_number=1,
        char_count=10,
        status="success",
        raw_solution_text="x = 2, 3",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def test_owner_can_create_public_share_and_get_url():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_1@example.com")
        attempt = _seed_attempt(session, owner.id)

    headers = _auth_header(client, "owner_share_1@example.com")
    resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attempt_id"] == attempt.attempt_id
    assert body["visibility"] == "PUBLIC"
    assert isinstance(body["share_url"], str) and "/share/" in body["share_url"]
    assert body["revoked"] is False


def test_public_share_is_sanitized_and_read_only_payload():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_2@example.com")
        attempt = _seed_attempt(session, owner.id, with_private_fields=True)

    headers = _auth_header(client, "owner_share_2@example.com")
    create_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    assert create_resp.status_code == 200, create_resp.text
    share_url = create_resp.json()["share_url"]
    token = share_url.rstrip("/").split("/")[-1]

    public_resp = client.get(f"/api/v1/shares/public/{token}")
    assert public_resp.status_code == 200, public_resp.text
    payload = public_resp.json()
    assert payload["attempt_id"] == attempt.attempt_id
    assert payload["visibility"] == "PUBLIC"
    assert "paper" in payload and isinstance(payload["paper"], dict)
    assert "problem" in payload and isinstance(payload["problem"], dict)

    serialized = str(payload).lower()
    assert "user_id" not in serialized
    assert "request_id" not in serialized
    assert "provider" not in serialized
    assert "total_tokens" not in serialized


def test_toggle_private_revokes_link_and_public_returns_404():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_3@example.com")
        attempt = _seed_attempt(session, owner.id)

    headers = _auth_header(client, "owner_share_3@example.com")
    create_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    token = create_resp.json()["share_url"].rstrip("/").split("/")[-1]

    disable_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PRIVATE"},
    )
    assert disable_resp.status_code == 200, disable_resp.text
    assert disable_resp.json()["visibility"] == "PRIVATE"
    assert disable_resp.json()["share_url"] is None

    public_resp = client.get(f"/api/v1/shares/public/{token}")
    assert public_resp.status_code == 404


def test_non_owner_cannot_create_share_for_other_attempt():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_4@example.com")
        other = _create_user(session, "other_share_4@example.com")
        attempt = _seed_attempt(session, owner.id)
        assert other.id != owner.id

    headers = _auth_header(client, "other_share_4@example.com")
    resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    assert resp.status_code == 403


def test_deleted_attempt_returns_404_on_public_link():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_5@example.com")
        attempt = _seed_attempt(session, owner.id)

    headers = _auth_header(client, "owner_share_5@example.com")
    create_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    token = create_resp.json()["share_url"].rstrip("/").split("/")[-1]

    with Session(engine) as session:
        row = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt.attempt_id)).first()
        assert row is not None
        session.delete(row)
        session.commit()

    public_resp = client.get(f"/api/v1/shares/public/{token}")
    assert public_resp.status_code == 404


def test_view_count_increments_on_public_views():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_6@example.com")
        attempt = _seed_attempt(session, owner.id)

    headers = _auth_header(client, "owner_share_6@example.com")
    create_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    token = create_resp.json()["share_url"].rstrip("/").split("/")[-1]

    first = client.get(f"/api/v1/shares/public/{token}")
    second = client.get(f"/api/v1/shares/public/{token}")
    assert first.status_code == 200
    assert second.status_code == 200

    with Session(engine) as session:
        share = session.exec(select(SolutionShare).where(SolutionShare.attempt_id == attempt.attempt_id)).first()
        assert share is not None
        assert int(share.view_count or 0) >= 2
        assert share.last_viewed_at is not None


def test_public_token_works_when_hash_missing_backfill():
    app, engine = _build_app()
    client = TestClient(app)
    with Session(engine) as session:
        owner = _create_user(session, "owner_share_7@example.com")
        attempt = _seed_attempt(session, owner.id)

    headers = _auth_header(client, "owner_share_7@example.com")
    create_resp = client.post(
        f"/api/v1/shares/attempt/{attempt.attempt_id}",
        headers=headers,
        json={"visibility": "PUBLIC"},
    )
    assert create_resp.status_code == 200, create_resp.text
    share_url = create_resp.json()["share_url"]
    token = share_url.rstrip("/").split("/")[-1]

    with Session(engine) as session:
        share = session.exec(select(SolutionShare).where(SolutionShare.attempt_id == attempt.attempt_id)).first()
        assert share is not None
        share.share_token_hash = None
        session.add(share)
        session.commit()

    public_resp = client.get(f"/api/v1/shares/public/{token}")
    assert public_resp.status_code == 200, public_resp.text
