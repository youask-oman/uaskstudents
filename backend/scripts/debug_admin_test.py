"""Run admin test inline to capture error."""
import os
import sys
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "DEV"
os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"

from seed_production import run_seed
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.database import engine
from app.main import app
from app.models import User
from app.auth import get_password_hash

try:
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)
    print("Seed OK")
    
    client = TestClient(app, raise_server_exceptions=False)
    
    # Login as admin
    resp = client.post("/api/v1/login", json={"email": "admin@uask.ai", "password": "DevOnlyChangeMe123!"})
    print(f"Admin login: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Body: {resp.text}")
        sys.exit(1)
    
    token = resp.json()["access_token"]
    admin_header = {"Authorization": f"Bearer {token}"}
    
    # Get first internal user
    with Session(engine) as session:
        first_internal = session.exec(
            select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai")).order_by(User.id.asc())
        ).first()
        assert first_internal is not None, "No internal user found"
        user_id = first_internal.id
        print(f"First internal user: {first_internal.email} (id={user_id})")

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
        status = "OK" if resp.status_code == 200 else f"FAIL({resp.status_code})"
        body_snippet = resp.text[:150] if resp.status_code != 200 else ""
        print(f"  {status} {path} {body_snippet}")
    
    print("ALL DONE")
    
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
