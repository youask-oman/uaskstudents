
import requests
import sys
import os

# Adjust path if needed, though running as script usually works relative to current dir
BASE_URL = "http://localhost:8000"

# Mock login or token generation?
# Since we have `get_staff_user`, checking `Authorization` header.
# We need a valid JWT token. 
# We can use `scripts/create_dev_token.py` if it exists, or generate one using `jose`.

import time
from jose import jwt
from datetime import datetime, timedelta

# Hardcoded secret from app/auth.py or env. 
# We'll assume a default or try to import it.
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Try to import SECRET_KEY
try:
    from app.auth import SECRET_KEY, ALGORITHM
except ImportError:
    print("Could not import SECRET_KEY, using fallback/env")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ALGORITHM = "HS256"

def create_test_token(email="admin@uask.ai", role="admin"):
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"sub": email, "exp": expire, "role": role}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def test_endpoints():
    token = create_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        "/api/admin/payments/overview",
        "/api/admin/payments/requests",
        "/api/admin/payments/invoices",
        "/api/admin/payments/subscriptions"
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting {endpoint}...")
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text}")
            else:
                # Print first 100 chars of success
                print(f"Success: {response.text[:100]}...")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    test_endpoints()
