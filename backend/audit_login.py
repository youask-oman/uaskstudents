import sys
import requests
from sqlmodel import Session, select
from app.database import engine
from app.models import User
from app.auth import verify_password
import time
import threading
import uvicorn
from app.main import app

def check_db_user():
    print("--- Database Audit ---")
    try:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == "final@uask.ai")).first()
            if not user:
                print("❌ User 'final@uask.ai' NOT FOUND in database.")
                return False
            print(f"✅ User found: {user.email}")
            print(f"   Role: {user.role}")
            print(f"   Password Hash: {user.password_hash[:10]}...")
            
            # Verify password locally
            if verify_password("password", user.password_hash):
                print("✅ Password verification (internal) PASSED")
            else:
                print("❌ Password verification (internal) FAILED")
                return False
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_api_login():
    print("\n--- API Audit ---")
    url = "http://localhost:8000/api/v1/login"
    payload = {"email": "final@uask.ai", "password": "password"}
    try:
        print(f"POST {url} with {payload}")
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print("✅ Login API Success!")
            print(f"   Token: {resp.json().get('access_token')[:10]}...")
            return True
        else:
            print(f"❌ Login API Failed: {resp.status_code}")
            print(f"   Response: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return False

if __name__ == "__main__":
    # 1. Check DB
    if not check_db_user():
        sys.exit(1)
        
    # 2. Start Server in background for test
    def run_server():
        uvicorn.run(app, port=8000, log_level="error")
        
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(5) # Wait for startup
    
    # 3. Test API
    if test_api_login():
        print("\n✅ AUDIT PASSED: Backend is fully functional.")
        sys.exit(0)
    else:
        print("\n❌ AUDIT FAILED: API issue.")
        sys.exit(1)
