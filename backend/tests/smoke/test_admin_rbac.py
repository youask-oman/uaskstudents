import json
import os
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import User
from app.database import engine
from scripts.seed_production import run_seed


@pytest.fixture
def non_admin_headers():
    # Find or create a non-admin user
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "employee", User.is_internal == False)).first()
        if not user:
            from app.auth import get_password_hash
            user = User(
                email="test-non-admin@example.com",
                full_name="Test Non Admin",
                role="employee",
                is_internal=False,
                password_hash=get_password_hash("password123"),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        from app.auth import create_access_token
        from datetime import timedelta
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=timedelta(minutes=15)
        )
        return {"Authorization": f"Bearer {access_token}"}


def _manifest_path() -> Path:
    for parent in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        candidate = parent / "admin_nav_manifest.json"
        if candidate.exists():
            return candidate
    candidate = Path("/src/admin_nav_manifest.json")
    if candidate.exists():
        return candidate
    raise AssertionError("admin_nav_manifest.json not found in repo root or /src mount.")


def test_admin_rbac_enforcement(non_admin_headers):
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
    nav_items = manifest.get("nav_items", [])
    assert nav_items, "Manifest nav_items must not be empty"

    # Restrict to admin-only prefixes to avoid endpoints that are intentionally public.
    protected_prefixes = ("/api/admin/billing", "/api/v1/admin")
    protected_paths = []
    for item in nav_items:
        if item.get("type") != "link":
            continue
        for path in item.get("api_checks", []) or []:
            if path.startswith(protected_prefixes):
                protected_paths.append(path)

    assert protected_paths, "No protected admin endpoints found for RBAC check."

    client = TestClient(app)
    for path in protected_paths:
        resp = client.get(path, headers=non_admin_headers)
        assert resp.status_code in (401, 403), f"{path}: expected 401/403, got {resp.status_code}"
