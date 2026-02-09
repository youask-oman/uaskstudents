import os

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import get_password_hash
from app.database import engine
from app.main import app
from app.models import User
from scripts.seed_production import run_seed


def _auth_header(email: str, password: str) -> dict:
    client = TestClient(app)
    resp = client.post("/api/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ensure_non_admin_user() -> tuple[str, str]:
    email = "student-smoke@uask.ai"
    password = "StudentSmoke123!"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            session.add(
                User(
                    email=email,
                    full_name="Smoke Student",
                    password_hash=get_password_hash(password),
                    role="student",
                    is_verified=True,
                )
            )
            session.commit()
        return email, password


def test_admin_billing_routes_access_matrix():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    client = TestClient(app)
    admin_header = _auth_header("admin@uask.ai", "DevOnlyChangeMe123!")

    with Session(engine) as session:
        first_internal = session.exec(
            select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai")).order_by(User.id.asc())
        ).first()
        assert first_internal is not None
        user_id = first_internal.id

    endpoints = [
        "/health",
        "/admin/billing/flags",
        "/admin/billing/programs",
        f"/admin/billing/users/{user_id}/wallet",
        "/admin/billing/ledger",
        "/admin/billing/holds",
        "/admin/billing/refunds",
        "/admin/billing/health",
        "/admin/billing/invoices",
    ]

    for path in endpoints:
        headers = admin_header if path != "/health" else None
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text}"

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    protected = [
        "/admin/billing/flags",
        "/admin/billing/programs",
        f"/admin/billing/users/{user_id}/wallet",
        "/admin/billing/ledger",
        "/admin/billing/holds",
        "/admin/billing/refunds",
        "/admin/billing/health",
        "/admin/billing/invoices",
    ]
    for path in protected:
        resp = client.get(path, headers=non_admin_header)
        assert resp.status_code == 403, f"{path}: expected 403, got {resp.status_code}"
