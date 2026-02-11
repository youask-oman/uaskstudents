from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api import api_router
from app.api_admin import legal_router
from app.auth import get_password_hash
from app.database import get_session
from app.models import LegalAcceptance, LegalDocument, User


def _build_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(legal_router)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    return app, engine


def test_login_shows_terms_required_then_acceptance_clears_requirement():
    app, engine = _build_app()
    with Session(engine) as session:
        session.add(
            User(
                email="student@example.com",
                full_name="Student",
                password_hash=get_password_hash("password123"),
                role="student",
            )
        )
        session.add(
            LegalDocument(
                key="terms_of_service",
                version="20260211",
                status="published",
                content_md="# Terms",
                content_html="<h1>Terms</h1>",
                published_at=datetime.now(timezone.utc),
                effective_at=datetime.now(timezone.utc),
                checksum_sha256="x",
            )
        )
        session.commit()

    client = TestClient(app)
    login = client.post("/api/v1/login", json={"email": "student@example.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert login.json()["terms_acceptance_required"] is True
    assert login.json()["required_terms_version"] == "20260211"

    accept = client.post(
        "/api/legal/accept",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "document_key": "terms_of_service",
            "document_version": "20260211",
            "method": "login",
            "locale": "en-CA",
        },
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    status = client.get("/api/legal/status", headers={"Authorization": f"Bearer {token}"})
    assert status.status_code == 200
    assert status.json()["requires_terms_acceptance"] is False
    assert status.json()["latest_accepted"]["terms_of_service"]["version"] == "20260211"

    with Session(engine) as session:
        row = session.exec(
            select(LegalAcceptance).where(
                LegalAcceptance.document_key == "terms_of_service",
                LegalAcceptance.document_version == "20260211",
            )
        ).first()
        assert row is not None
        assert row.method == "login"
        assert row.locale == "en-CA"


def test_signup_requires_legal_flags_and_records_signup_acceptances():
    app, engine = _build_app()
    with Session(engine) as session:
        session.add(
            LegalDocument(
                key="terms_of_service",
                version="20260211",
                status="published",
                content_md="# Terms",
                content_html="<h1>Terms</h1>",
                published_at=datetime.now(timezone.utc),
                effective_at=datetime.now(timezone.utc),
                checksum_sha256="x",
            )
        )
        session.add(
            LegalDocument(
                key="privacy_policy",
                version="20260211",
                status="published",
                content_md="# Privacy",
                content_html="<h1>Privacy</h1>",
                published_at=datetime.now(timezone.utc),
                effective_at=datetime.now(timezone.utc),
                checksum_sha256="y",
            )
        )
        session.commit()

    client = TestClient(app)

    denied = client.post(
        "/api/v1/signup",
        json={
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User",
            "terms_accepted": False,
            "privacy_acknowledged": False,
        },
    )
    assert denied.status_code == 400

    ok = client.post(
        "/api/v1/signup",
        json={
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User",
            "terms_accepted": True,
            "privacy_acknowledged": True,
        },
    )
    assert ok.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "newuser@example.com")).first()
        assert user is not None
        rows = session.exec(select(LegalAcceptance).where(LegalAcceptance.user_id == user.id)).all()
        keys = sorted((r.document_key, r.method) for r in rows)
        assert ("privacy_policy", "signup") in keys
        assert ("terms_of_service", "signup") in keys


def test_checkout_requires_latest_terms_acceptance():
    app, engine = _build_app()
    with Session(engine) as session:
        user = User(
            email="checkout@example.com",
            full_name="Checkout User",
            password_hash=get_password_hash("password123"),
            role="student",
        )
        session.add(user)
        session.flush()
        session.add(
            LegalDocument(
                key="terms_of_service",
                version="20260211",
                status="published",
                content_md="# Terms",
                content_html="<h1>Terms</h1>",
                published_at=datetime.now(timezone.utc),
                effective_at=datetime.now(timezone.utc),
                checksum_sha256="x",
            )
        )
        session.commit()
        user_id = user.id

    client = TestClient(app)
    resp = client.post(
        f"/api/v1/subscriptions/stripe/checkout?user_id={user_id}",
        json={
            "plan_slug": "student_standard",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
    )
    assert resp.status_code == 428
