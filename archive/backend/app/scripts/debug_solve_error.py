import requests
import json
import sys
import os

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")
STUDENT_EMAIL = "student100@uask.ai"
STUDENT_PASSWORD = "password123"
PROBLEM_TEXT = "$$ \\text{line }(1,1),(2,4) $$"

def login():
    res = requests.post(f"{API_URL}/login", json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD})
    if res.status_code != 200:
        print(f"❌ Login failed: {res.text}")
        sys.exit(1)
    return res.json()

def debug_solve():
    print(f"🔐 Logging in as {STUDENT_EMAIL}...")
    auth = login()
    token = auth['access_token']
    user_id = auth['user_id']
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "text_query": PROBLEM_TEXT,
        "mode": "debug" # Request debug mode to hopefully get more info or trigger trace
    }
    
    print(f"📤 Submitting problem: {PROBLEM_TEXT}")
    print(f"   User ID: {user_id}")
    
    url = f"{API_URL}/solve_v3?user_id={user_id}"
    try:
        res = requests.post(url, json=payload, headers=headers)
        
        print(f"\n📥 Response Status: {res.status_code}")
        try:
            data = res.json()
            print(json.dumps(data, indent=2))
            
            if data.get("error"):
                print(f"\n❌ API Returned Error Flag: {data.get('error_type')}")
        except:
            print(f"Response Text: {res.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    debug_solve()
