from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api_admin import admin_router, legal_router, get_admin_user
from app.database import get_session
from app.models import User


def _build_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(legal_router)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_admin_user] = lambda: User(
        id=1,
        email="admin@uask.ai",
        full_name="Admin",
        password_hash="x",
        role="admin",
    )
    return app


def test_publish_and_select_latest_published_version():
    app = _build_test_app()
    client = TestClient(app)

    create_a = client.post(
        "/api/admin/legal-documents",
        json={"key": "privacy_policy", "content_md": "# A", "version": "20260211"},
    )
    assert create_a.status_code == 200
    id_a = create_a.json()["id"]
    pub_a = client.post(f"/api/admin/legal-documents/{id_a}/publish")
    assert pub_a.status_code == 200

    create_b = client.post(
        "/api/admin/legal-documents",
        json={"key": "privacy_policy", "content_md": "# B", "version": "20260212"},
    )
    assert create_b.status_code == 200
    id_b = create_b.json()["id"]
    pub_b = client.post(
        f"/api/admin/legal-documents/{id_b}/publish",
        json={"effective_at": datetime(2026, 2, 12).isoformat()},
    )
    assert pub_b.status_code == 200

    latest = client.get("/api/legal/privacy")
    assert latest.status_code == 200
    assert latest.json()["version"] == "20260212"

    old = client.get("/api/legal/privacy?version=20260211")
    assert old.status_code == 200
    assert old.json()["content_md"] == "# A"

    by_path = client.get("/api/legal/privacy/v/20260211")
    assert by_path.status_code == 200
    assert by_path.json()["version"] == "20260211"


def test_editing_published_document_creates_new_draft():
    app = _build_test_app()
    client = TestClient(app)

    created = client.post(
        "/api/admin/legal-documents",
        json={"key": "privacy_policy", "content_md": "# Original", "version": "20260211"},
    )
    assert created.status_code == 200
    original_id = created.json()["id"]

    published = client.post(f"/api/admin/legal-documents/{original_id}/publish")
    assert published.status_code == 200

    update = client.put(
        "/api/admin/legal-documents",
        json={"id": original_id, "key": "privacy_policy", "content_md": "# Edited"},
    )
    assert update.status_code == 200
    payload = update.json()
    assert payload["status"] == "created"
    assert payload["id"] != original_id

    original = client.get(f"/api/admin/legal-documents/{original_id}")
    assert original.status_code == 200
    assert original.json()["status"] == "published"
    assert original.json()["content_md"] == "# Original"

    new_doc = client.get(f"/api/admin/legal-documents/{payload['id']}")
    assert new_doc.status_code == 200
    assert new_doc.json()["status"] == "draft"
    assert new_doc.json()["content_md"] == "# Edited"
