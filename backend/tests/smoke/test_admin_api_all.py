import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import User
from scripts.seed_production import run_seed


def _manifest_path() -> Path:
    for parent in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        candidate = parent / "admin_nav_manifest.json"
        if candidate.exists():
            return candidate
    candidate = Path("/src/admin_nav_manifest.json")
    if candidate.exists():
        return candidate
    raise AssertionError("admin_nav_manifest.json not found in repo root or /src mount.")


def _auth_header(email: str, password: str) -> dict:
    client = TestClient(app)
    resp = client.post("/api/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_superadmin_email() -> str:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "superadmin")).first()
        assert user is not None, "No seeded superadmin user found."
        return user.email


def test_admin_api_checks_from_manifest():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
    nav_items = manifest.get("nav_items", [])
    assert nav_items, "Manifest nav_items must not be empty"

    api_checks = []
    for item in nav_items:
        if item.get("type") != "link":
            continue
        for path in item.get("api_checks", []) or []:
            api_checks.append(path)

    if not api_checks:
        raise AssertionError("Manifest api_checks must include at least one endpoint.")

    superadmin_email = _get_superadmin_email()
    password = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    headers = _auth_header(superadmin_email, password)
    client = TestClient(app)

    for path in api_checks:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text}"
