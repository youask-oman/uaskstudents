import os
from datetime import datetime

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


def _ensure_superadmin_user() -> tuple[str, str]:
    password = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "superadmin")).first()
        assert user is not None, "No superadmin user seeded."
        return user.email, password


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
        "/api/admin/billing/flags",
        "/api/admin/billing/programs",
        f"/api/admin/billing/users/{user_id}/wallet_summary",
        f"/api/admin/billing/users/{user_id}/lots",
        f"/api/admin/billing/users/{user_id}/ledger",
        f"/api/admin/billing/users/{user_id}/enrollments",
        "/api/admin/billing/ledger",
        "/api/admin/billing/holds",
        "/api/admin/billing/refunds",
        "/api/admin/billing/health",
        "/api/admin/billing/invoices",
        "/api/admin/billing/pricing",
    ]

    for path in endpoints:
        headers = admin_header if path != "/health" else None
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text}"

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    protected = [
        "/api/admin/billing/flags",
        "/api/admin/billing/programs",
        f"/api/admin/billing/users/{user_id}/wallet_summary",
        f"/api/admin/billing/users/{user_id}/lots",
        f"/api/admin/billing/users/{user_id}/ledger",
        f"/api/admin/billing/users/{user_id}/enrollments",
        "/api/admin/billing/ledger",
        "/api/admin/billing/holds",
        "/api/admin/billing/refunds",
        "/api/admin/billing/health",
        "/api/admin/billing/invoices",
        "/api/admin/billing/pricing",
    ]
    for path in protected:
        resp = client.get(path, headers=non_admin_header)
        assert resp.status_code == 403, f"{path}: expected 403, got {resp.status_code}"


def test_admin_billing_mutations_superadmin_only():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    client = TestClient(app)
    superadmin_email, superadmin_password = _ensure_superadmin_user()
    superadmin_header = _auth_header(superadmin_email, superadmin_password)

    with Session(engine) as session:
        target = session.exec(
            select(User).where(User.is_internal == True).order_by(User.id.asc())
        ).first()
        assert target is not None
        user_id = target.id

    stamp = int(datetime.utcnow().timestamp())
    grant_resp = client.post(
        f"/api/admin/billing/users/{user_id}/grant",
        headers=superadmin_header,
        json={
            "credits": 10,
            "reason": "smoke grant",
            "lot_type": "ADJUSTMENT",
            "expires_days": 30,
            "idempotency_key": f"smoke_grant_{user_id}_{stamp}",
        },
    )
    assert grant_resp.status_code == 200, grant_resp.text

    refund_resp = client.post(
        f"/api/admin/billing/users/{user_id}/refund",
        headers=superadmin_header,
        json={
            "credits": 2,
            "reason": "smoke refund",
            "reason_code": "SERVICE_ISSUE",
            "source_payment_id": f"pay_smoke_{stamp}",
            "source_attempt_id": f"attempt_smoke_{stamp}",
            "idempotency_key": f"smoke_refund_{user_id}_{stamp}",
        },
    )
    assert refund_resp.status_code == 200, refund_resp.text

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    denied_resp = client.post(
        f"/api/admin/billing/users/{user_id}/grant",
        headers=non_admin_header,
        json={
            "credits": 1,
            "reason": "should fail",
            "lot_type": "ADJUSTMENT",
            "expires_days": 30,
            "idempotency_key": f"smoke_grant_denied_{user_id}_{stamp}",
        },
    )
    assert denied_resp.status_code == 403, f"expected 403, got {denied_resp.status_code}"


def test_admin_billing_reconcile_access():
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

    resp = client.post(
        f"/api/admin/billing/users/{user_id}/reconcile",
        headers=admin_header,
        json={"reason": "smoke test reconcile", "idempotency_key": f"smoke_reconcile_{user_id}"},
    )
    assert resp.status_code == 200, resp.text

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    resp = client.post(
        f"/api/admin/billing/users/{user_id}/reconcile",
        headers=non_admin_header,
        json={"reason": "should fail", "idempotency_key": f"smoke_reconcile_{user_id}_na"},
    )
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}"
