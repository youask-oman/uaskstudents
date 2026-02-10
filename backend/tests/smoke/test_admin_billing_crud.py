import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

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


def _get_superadmin() -> User:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "superadmin")).first()
        assert user is not None, "No seeded superadmin user found."
        return user


def _get_target_user_id() -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.is_internal == True).order_by(User.id.asc())).first()
        assert user is not None, "No internal user found."
        return user.id


def test_admin_billing_crud_endpoints():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    client = TestClient(app)
    superadmin = _get_superadmin()
    headers = _auth_header(superadmin.email, os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!"))
    user_id = _get_target_user_id()
    stamp = int(datetime.utcnow().timestamp())

    grant_resp = client.post(
        f"/api/admin/billing/users/{user_id}/grant",
        headers=headers,
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
        headers=headers,
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

    reconcile_resp = client.post(
        f"/api/admin/billing/users/{user_id}/reconcile",
        headers=headers,
        json={
            "reason": "smoke reconcile",
            "idempotency_key": f"smoke_reconcile_{user_id}_{stamp}",
        },
    )
    assert reconcile_resp.status_code == 200, reconcile_resp.text

    slug = f"smoke_program_{stamp}"
    program_resp = client.post(
        "/api/admin/billing/programs",
        headers=headers,
        json={
            "name": f"Smoke Program {stamp}",
            "slug": slug,
            "description": "Smoke test program",
            "status": "active",
            "monthly_gift_credits": 25,
            "gift_expiry_window_days": 30,
            "entitlements": {"tier": "STANDARD"},
            "reason": "smoke create program",
            "idempotency_key": f"smoke_program_create_{stamp}",
        },
    )
    assert program_resp.status_code == 200, program_resp.text
    program_id = program_resp.json()["id"]

    update_resp = client.put(
        f"/api/admin/billing/programs/{program_id}",
        headers=headers,
        json={
            "name": f"Smoke Program {stamp} Updated",
            "description": "Smoke test program updated",
            "status": "inactive",
            "reason": "smoke update program",
            "idempotency_key": f"smoke_program_update_{stamp}",
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    delete_resp = client.request(
        "DELETE",
        f"/api/admin/billing/programs/{program_id}",
        headers=headers,
        json={
            "reason": "smoke archive program",
            "idempotency_key": f"smoke_program_delete_{stamp}",
        },
    )
    assert delete_resp.status_code == 200, delete_resp.text

    pricing_resp = client.post(
        "/api/admin/billing/pricing",
        headers=headers,
        json={
            "pricing": {
                "provider": "openai",
                "model": "gpt-5-mini",
                "price_in_per_1m": 0.25,
                "price_out_per_1m": 0.5,
                "price_cached_in_per_1m": 0.05,
                "currency": "USD",
                "effective_from": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            },
            "reason": "smoke pricing update",
            "idempotency_key": f"smoke_pricing_{stamp}",
        },
    )
    assert pricing_resp.status_code == 200, pricing_resp.text

    pack_code = f"smoke_pack_{stamp}"
    pack_resp = client.post(
        "/api/admin/billing/packs",
        headers=headers,
        json={
            "code": pack_code,
            "name": f"Smoke Pack {stamp}",
            "credits": 500,
            "price_usd": 9.99,
            "is_active": True,
            "description": "Smoke test pack",
            "reason": "smoke create pack",
            "idempotency_key": f"smoke_pack_create_{stamp}",
        },
    )
    assert pack_resp.status_code == 200, pack_resp.text
    pack_id = pack_resp.json()["id"]

    pack_update_resp = client.put(
        f"/api/admin/billing/packs/{pack_id}",
        headers=headers,
        json={
            "name": f"Smoke Pack {stamp} Updated",
            "credits": 750,
            "price_usd": 12.99,
            "description": "Smoke test pack updated",
            "reason": "smoke update pack",
            "idempotency_key": f"smoke_pack_update_{stamp}",
        },
    )
    assert pack_update_resp.status_code == 200, pack_update_resp.text

    pack_delete_resp = client.request(
        "DELETE",
        f"/api/admin/billing/packs/{pack_id}",
        headers=headers,
        json={
            "reason": "smoke deactivate pack",
            "idempotency_key": f"smoke_pack_delete_{stamp}",
        },
    )
    assert pack_delete_resp.status_code == 200, pack_delete_resp.text
