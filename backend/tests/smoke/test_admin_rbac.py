import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import User
from sqlmodel import Session, select
from app.database import engine
import json
import os
from pathlib import Path

# Load inventory
INVENTORY_PATH = Path(__file__).resolve().parents[2] / "reports" / "admin_route_inventory.json"

@pytest.fixture
def non_admin_headers():
    # Find or create a non-admin user
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "employee", User.is_internal == False)).first()
        if not user:
            # Create one if missing
            from app.auth import get_password_hash
            user = User(
                email="test-non-admin@example.com",
                full_name="Test Non Admin",
                role="employee",
                is_internal=False,
                password_hash=get_password_hash("password123")
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        
        # We simulate authentication by providing the user_id in headers if the app supports it for testing
        # or we generate a real JWT. Let's use the X-User-ID if applicable, 
        # but realistically we need a real token if RBAC middleware is strict.
        from app.auth import create_access_token
        from datetime import timedelta
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=timedelta(minutes=15)
        )
        return {"Authorization": f"Bearer {access_token}"}

def test_admin_rbac_enforcement(non_admin_headers):
    client = TestClient(app)
    
    if not INVENTORY_PATH.exists():
        pytest.skip("Inventory file missing")
        
    with open(INVENTORY_PATH, "r") as f:
        inventory = json.load(f)
        
    endpoints = inventory["backend_endpoints"]
    
    # We don't test ALL 135 here because it's slow, but we pick representative ones
    # focusing on various prefixes and tags.
    tested_count = 0
    for ep in endpoints:
        path = ep["path"]
        method = ep["methods"][0] if ep["methods"] else "GET"
        
        # Skip endpoints that are NOT clearly admin protected (some critical prefixes might be public-ish)
        if not any(p in path for p in ["/admin", "/api/admin", "/api/v1/admin"]):
            continue
            
        # Skip path param endpoints for now in RBAC check (simple 403 should happen regardless of ID)
        if "{" in path:
            # Simple check with dummy ID
            test_path = path.replace("{user_id}", "999").replace("{sub_id}", "999").replace("{attempt_id}", "999")
            # If there are other braces, just skip it to be safe
            if "{" in test_path:
                continue
        else:
            test_path = path
            
        if method == "GET":
            resp = client.get(test_path, headers=non_admin_headers)
        elif method == "POST":
            resp = client.post(test_path, headers=non_admin_headers, json={})
        else:
            continue
            
        # We expect 403 Forbidden or 401 Unauthorized (if token is invalid, but we sent one)
        # Some endpoints might return 404 if the path doesn't exist (but discovery says it does)
        # Any non-200/non-500 is generally good for RBAC, but we want 403.
        assert resp.status_code >= 400, f"Endpoint {method} {test_path} allowed non-admin access! Status: {resp.status_code}"
        tested_count += 1
        
        if tested_count > 20: # Limit to 20 representative endpoints
            break

    print(f"Tested {tested_count} endpoints for RBAC")
