import os

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import User
from scripts.seed_production import run_seed
from tests.smoke.test_admin_routes import _auth_header, _ensure_non_admin_user, _ensure_superadmin_user


def test_admin_payments_routes_access_matrix():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    try:
        run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)
    except RuntimeError as e:
        # Allow running when payments already exist in dev
        if "Payment table is not empty" not in str(e):
            raise

    client = TestClient(app)
    admin_header = _auth_header("admin@uask.ai", os.environ["SEED_DEV_DEFAULT_PASSWORD"])

    endpoints = [
        "/api/admin/payments/overview",
        "/api/admin/payments/requests",
        "/api/admin/payments/topups",
        "/api/admin/payments/subscriptions",
        "/api/admin/payments/invoices",
        "/api/admin/payments/stripe/events",
        "/api/admin/payments/reconciliation",
        "/api/admin/payments/config",
        "/api/admin/payments/pricing",
        "/api/admin/payments/stripe/health",
    ]

    for path in endpoints:
        resp = client.get(path, headers=admin_header)
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text}"

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    for path in endpoints:
        resp = client.get(path, headers=non_admin_header)
        assert resp.status_code == 403, f"{path}: expected 403, got {resp.status_code}"


def test_admin_payments_reconciliation_run_superadmin_only():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    try:
        run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)
    except RuntimeError as e:
        if "Payment table is not empty" not in str(e):
            raise

    client = TestClient(app)
    superadmin_email, superadmin_password = _ensure_superadmin_user()
    superadmin_header = _auth_header(superadmin_email, superadmin_password)

    resp = client.post(
        "/api/admin/payments/reconciliation/run",
        headers=superadmin_header,
        json={"confirm": "RUN_RECONCILIATION", "reason": "smoke"},
    )
    assert resp.status_code == 200, resp.text

    non_admin_email, non_admin_password = _ensure_non_admin_user()
    non_admin_header = _auth_header(non_admin_email, non_admin_password)
    resp = client.post(
        "/api/admin/payments/reconciliation/run",
        headers=non_admin_header,
        json={"confirm": "RUN_RECONCILIATION", "reason": "should fail"},
    )
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}"
