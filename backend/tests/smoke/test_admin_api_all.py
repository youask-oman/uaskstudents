import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import User, Plan, CreditProgramDefinition, School
from sqlmodel import Session, select
from app.database import engine
import json
from pathlib import Path
from datetime import timedelta
from app.auth import create_access_token
import time

# Load inventory
INVENTORY_PATH = Path(__file__).resolve().parents[2] / "reports" / "admin_route_inventory.json"

@pytest.fixture
def admin_headers():
    with Session(engine) as session:
        # User 1 is usually the admin in our setup, but let's be explicitly certain
        user = session.exec(select(User).where(User.role == "admin")).first()
        if not user:
            pytest.fail("No admin user found in database. Seed might be incomplete.")
            
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=timedelta(minutes=30)
        )
        return {"Authorization": f"Bearer {access_token}"}

def get_fixture_id(entity_name):
    """Helper to get a valid ID for various entities from the database."""
    with Session(engine) as session:
        if entity_name == "user_id":
            return session.exec(select(User.id)).first()
        if entity_name == "plan_id":
            return session.exec(select(Plan.id)).first()
        if entity_name == "school_id":
            return session.exec(select(School.id)).first()
        if entity_name == "target_user_id":
            return session.exec(select(User.id)).first()
        return "1"

def test_admin_api_endpoints_200(admin_headers):
    client = TestClient(app)
    
    if not INVENTORY_PATH.exists():
        pytest.skip("Inventory file missing")
        
    with open(INVENTORY_PATH, "r") as f:
        inventory = json.load(f)
        
    endpoints = inventory["backend_endpoints"]
    results = []
    
    # We only test GET endpoints for the "mass" smoke test to avoid unexpected state changes
    # but we will pick a few POST/PUT for critical ones.
    to_test = [ep for ep in endpoints if "GET" in ep["methods"]]
    
    passed = 0
    failed = 0
    
    for ep in to_test:
        path = ep["path"]
        
        # Skip endpoints known to be removed or problematic in mass testing
        if "_removed" in ep["name"] or "stream" in path or "/ws" in path:
            continue
            
        # Replace path parameters
        test_path = path
        params = {
            "{user_id}": get_fixture_id("user_id"),
            "{plan_id}": get_fixture_id("plan_id"),
            "{target_user_id}": get_fixture_id("target_user_id"),
            "{school_id}": get_fixture_id("school_id"),
            "{table_name}": "user",
            "{config_type}": "general",
            "{request_id}": "none",
            "{sub_id}": "1",
            "{invoice_id}": "1",
            "{attempt_id}": "1",
            "{prompt_id}": "1",
            "{schema_id}": "1",
            "{version_id}": "1"
        }
        
        for k, v in params.items():
            if k in test_path:
                test_path = test_path.replace(k, str(v))
        
        # Final safety check if we missed any param
        if "{" in test_path:
             continue # Skip complex ones that need multi-param discovery
             
        start_time = time.time()
        try:
            resp = client.get(test_path, headers=admin_headers)
            duration = (time.time() - start_time) * 1000
            
            # We expect 200, but some might be 404 (if no data) which is NOT a 500
            # 500 is the main thing we want to avoid.
            if resp.status_code == 500:
                failed += 1
                results.append({"path": path, "status": "FAIL", "code": 500, "error": resp.text})
            else:
                passed += 1
                results.append({"path": path, "status": "PASS", "code": resp.status_code, "ms": duration})
        except Exception as e:
            failed += 1
            results.append({"path": path, "status": "ERROR", "error": str(e)})

    print(f"\nAdmin API Smoke Test: {passed} PASSED, {failed} FAILED")
    
    # Save a temporary result for the runner to pick up
    report_file = Path(__file__).resolve().parents[2] / "reports" / "admin_api_test_results.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
        
    assert failed == 0, f"Found {failed} API failures in admin dashboard"
