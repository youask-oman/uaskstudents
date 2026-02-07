
import sys
import os
import requests
from sqlalchemy import inspect
# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database import engine
from app.auth import SECRET_KEY, ALGORITHM
from jose import jwt
from datetime import datetime, timedelta

def create_test_token(email="admin@uask.ai", role="admin"):
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"sub": email, "exp": expire, "role": role}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def check_schema():
    print("\n--- SCHEMA CHECK ---")
    insp = inspect(engine)
    if insp.has_table("systemerrorentry"):
        cols = [c['name'] for c in insp.get_columns("systemerrorentry")]
        required = ["severity", "trace_id", "error_code"]
        missing = [col for col in required if col not in cols]
        if missing:
            print(f"FAIL: Missing columns in SystemErrorEntry: {missing}")
        else:
            print("PASS: SystemErrorEntry schema looks correct.")
    else:
        print("FAIL: systemerrorentry table does not exist")

def check_endpoints():
    print("\n--- ENDPOINT CHECK ---")
    token = create_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    base_url = "http://localhost:8000"

    # Check Overview
    print("Checking /api/admin/payments/overview...")
    try:
        r = requests.get(f"{base_url}/api/admin/payments/overview", headers=headers)
        if r.status_code == 200:
            print("PASS: /overview returned 200 OK")
        else:
            print(f"FAIL: /overview returned {r.status_code}")
            print(r.text)
    except Exception as e:
        print(f"FAIL: Request error: {e}")

    # Check Invoice HTML (need an invoice ID)
    # First get list of invoices
    print("Checking /api/admin/payments/invoices...")
    try:
        r = requests.get(f"{base_url}/api/admin/payments/invoices", headers=headers)
        if r.status_code == 200:
            data = r.json()
            invoices = data.get("invoices", [])
            if invoices:
                inv_id = invoices[0]["id"]
                print(f"Found invoice {inv_id}, checking HTML...")
                r_html = requests.get(f"{base_url}/api/admin/payments/invoices/{inv_id}/html", headers=headers)
                if r_html.status_code == 200:
                    print("PASS: /html endpoint returned 200 OK")
                else:
                    print(f"FAIL: /html endpoint returned {r_html.status_code}")
                    print(r_html.text)
            else:
                print("SKIP: No invoices found to test HTML endpoint")
        else:
            print(f"FAIL: /invoices returned {r.status_code}")
    except Exception as e:
        print(f"FAIL: Request error: {e}")

if __name__ == "__main__":
    check_schema()
    check_endpoints()
