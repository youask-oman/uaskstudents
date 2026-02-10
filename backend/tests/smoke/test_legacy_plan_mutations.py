import os

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import Plan, User
from scripts.seed_production import run_seed


def _auth_header(email: str, password: str) -> dict:
    client = TestClient(app)
    resp = client.post("/api/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_admin_email() -> str:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@uask.ai")).first()
        assert user is not None, "Seeded admin user missing."
        return user.email


def test_legacy_plan_mutations_blocked():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    admin_email = _get_admin_email()
    admin_header = _auth_header(admin_email, os.environ["SEED_DEV_DEFAULT_PASSWORD"])
    client = TestClient(app)

    with Session(engine) as session:
        plan = session.exec(select(Plan).order_by(Plan.id.asc())).first()
        assert plan is not None, "No plans seeded for legacy mutation test."
        plan_id = plan.id

    create_resp = client.post(
        "/api/v1/admin/plans",
        headers=admin_header,
        json={
            "name": "Legacy Blocked",
            "slug": "legacy-blocked",
            "credits_per_month": 1000,
            "price_monthly_cents": 999,
            "price_yearly_cents": 9999,
            "seats": 1,
            "features": {},
            "multipliers": {},
            "is_active": True,
        },
    )
    assert create_resp.status_code in (403, 410), create_resp.text

    delete_resp = client.delete(
        f"/api/v1/admin/plans/{plan_id}",
        headers=admin_header,
    )
    assert delete_resp.status_code in (403, 410), delete_resp.text
