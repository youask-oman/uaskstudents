import requests
import time
import random
import sys
import json
import os

# Configuration
API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")
STUDENT_PASSWORD = "password123"

# Range of seeded IDs
START_ID = 100
END_ID = 519

# Test Problems - ensuring they contain math symbols/digits
PROBLEMS = [
    "2 + 2 = 4",
    "x^2 + y^2 = 25",
    "15 * 3",
    "What is the capital of France? 123", # Adding digits to pass validation
    "Area = 3.14 * 5^2"
]

def get_random_student_creds():
    student_id = random.randint(START_ID, END_ID)
    email = f"student{student_id}@uask.ai"
    return email, STUDENT_PASSWORD

def login(email, password):
    try:
        response = requests.post(f"{API_URL}/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json()
        print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {e}")
        return None

def submit_solve(token, problem, student_profile, user_id):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "image": None,
        "text_query": problem,
        "time_limit": 30
    }
    
    print(f"   📤 Submitting: '{problem}'")
    print(f"   🌍 Context should use: {student_profile.get('profile_country')}, {student_profile.get('profile_province_state')}, {student_profile.get('grade_level')}")
    
    start_time = time.time()
    try:
        # Add user_id to query params as required by the endpoint signature
        url = f"{API_URL}/solve_v3?user_id={user_id}"
        response = requests.post(url, json=payload, headers=headers)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success ({duration:.2f}s)")
            return True, duration, data
        else:
            print(f"   ❌ Solve failed: {response.status_code} - {response.text}")
            return False, duration, None
            
    except Exception as e:
        print(f"   ❌ Request exception: {e}")
        return False, 0, None

def run_test_sequence():
    print("=" * 60)
    print(f"🚦 STARTING LIVE TRAFFIC TEST against {API_URL}")
    print("=" * 60)
    
    errors = 0
    
    # 1. Login Test
    email, password = get_random_student_creds()
    print(f"\n🔑 Authenticating as {email}...")
    auth_data = login(email, password)
    
    if not auth_data:
        print("❌ CRITICAL: Cannot login. Aborting.")
        sys.exit(1)
        
    access_token = auth_data['access_token']
    user_id = auth_data['user_id']
    
    # Fetch profile to confirm seeded data
    print(f"   👤 Fetching profile for user {user_id}...")
    try:
        profile_res = requests.get(f"{API_URL}/user/profile?user_id={user_id}", headers={"Authorization": f"Bearer {access_token}"})
        if profile_res.status_code != 200:
            print(f"❌ Failed to fetch profile: {profile_res.status_code}")
            sys.exit(1)
        
        profile = profile_res.json()
        print(f"   ✅ Profile loaded: {profile['full_name']} | {profile.get('profile_country')} | {profile.get('profile_province_state')}")
    except Exception as e:
        print(f"❌ Profile fetch exception: {e}")
        sys.exit(1)

    # 2. Functional Solve Test (Cold)
    problem = random.choice(PROBLEMS)
    print(f"\n🧠 Test 1: Cold Solve Request")
    success, duration_cold, result = submit_solve(access_token, problem, profile, user_id)
    
    if not success:
        errors += 1
    
    # 3. Cache Hit Test (Warm)
    print(f"\n⚡ Test 2: Warm Solve Request (Cache Check)")
    print(f"   🔄 Resubmitting same problem...")
    success, duration_warm, result_warm = submit_solve(access_token, problem, profile, user_id)
    
    if not success:
        errors += 1
    else:
        # Check if faster (simple heuristic for cache)
        # Note: In a real LLM app, cold might be 2-5s, warm < 0.5s
        print(f"   ⏱️  Cold: {duration_cold:.3f}s vs Warm: {duration_warm:.3f}s")
        if duration_warm < duration_cold:
            print(f"   ✅ Latency reduced by {duration_cold - duration_warm:.3f}s")
        else:
             print(f"   ⚠️  Warm request was not faster (Might be first cache miss or network variance)")

    # 4. Stress/Stability Check - 5 Sequential Requests
    print(f"\n🔄 Test 3: Stability Sequence (5 sequential requests)")
    for i in range(5):
        # Pick different students for each request to test auth load
        loop_email, _ = get_random_student_creds()
        loop_auth = login(loop_email, STUDENT_PASSWORD)
        if not loop_auth:
            errors += 1
            print(f"   ❌ Login failed for {loop_email}")
            continue
            
        prob = PROBLEMS[i % len(PROBLEMS)]
        loop_user_id = loop_auth['user_id']
        loop_token = loop_auth['access_token']
        
        # We assume the profile fetch works if login worked to keep this part fast
        # Just submitting
        print(f"   Request {i+1}/5: {loop_email} -> '{prob}'")
        ok, _, _ = submit_solve(loop_token, prob, {}, loop_user_id)
        if not ok:
            errors += 1

    print("\n" + "=" * 60)
    if errors == 0:
        print("✅ LIVE TRAFFIC TEST PASSED - ZERO ERRORS")
    else:
        print(f"❌ LIVE TRAFFIC TEST FAILED with {errors} errors")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    run_test_sequence()
