import os
import requests
import json
import time
import uuid

# Load .env manually
def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

load_env_file("e:/uaskstudents/.env")

BASE_URL = "http://localhost:8000/api/v1"
# We need a user ID. From previous DB check, 11 (olivia) or 15 exist.
USER_ID = 11

def log_result(f, text):
    print(text)
    f.write(text + "\n")

def run_tests():
    with open("e2e_validation_results.txt", "w") as report:
        log_result(report, "=== PHASE 1 E2E VALIDATION RESULTS ===")
        log_result(report, f"Timestamp: {time.ctime()}")
        log_result(report, f"User ID: {USER_ID}")
        
        # --- Scenario 1: Normal success solve ---
        log_result(report, "\n--- Scenario 1: Normal Success Solve ---")
        problem1 = "sqrt(x + 5) = x - 1"
        log_result(report, f"Input: {problem1}")
        
        res1 = requests.post(
            f"{BASE_URL}/solve_v3_stream",
            params={"user_id": USER_ID},
            json={
                "confirmed_text": problem1,
                "requested_mode": "minimal",
                "tier": "free",
                "features_used": {}
            },
            stream=True
        )
        
        attempt_id = None
        status = "unknown"
        for line in res1.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data = json.loads(line_str[6:])
                    if data.get("type") == "meta":
                        attempt_id = data.get("attempt_id")
                    if data.get("type") == "done":
                        if data.get("ok"): status = "success"
                        else: status = "failure"
        
        log_result(report, f"Received attempt_id: {attempt_id}")
        log_result(report, f"Done event status: {status}")
        
        # Verify via GET /attempt/{attempt_id}
        if attempt_id:
            att_res = requests.get(f"{BASE_URL}/attempt/{attempt_id}")
            att_data = att_res.json()
            log_result(report, f"GET /attempt/{attempt_id} Response:")
            log_result(report, json.dumps(att_data, indent=2))
            if att_data.get("status") == "success":
                log_result(report, "Scenario 1: SUCCESS")
            else:
                log_result(report, f"Scenario 1: FAILED (status={att_data.get('status')})")
        else:
            log_result(report, "Scenario 1: FAILED (no attempt_id)")

        # --- Scenario 2: Ambiguous input (clarify #1) ---
        log_result(report, "\n--- Scenario 2: Ambiguous Input (Clarification #1) ---")
        # 'x' is almost always ambiguous
        problem2 = "x" 
        log_result(report, f"Input: {problem2}")
        
        res2 = requests.post(
            f"{BASE_URL}/solve_v3_stream",
            params={"user_id": USER_ID},
            json={
                "confirmed_text": problem2,
                "requested_mode": "minimal",
                "tier": "free",
                "features_used": {}
            },
            stream=True
        )
        
        attempt_id2 = None
        status2 = "unknown"
        for line in res2.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data = json.loads(line_str[6:])
                    if data.get("type") == "meta":
                        attempt_id2 = data.get("attempt_id")
                    if data.get("type") == "done":
                        if data.get("error", {}).get("code") == "ambiguous_response":
                            status2 = "ambiguous"
                        else:
                            status2 = "success" if data.get("ok") else "failure"

        log_result(report, f"Received attempt_id: {attempt_id2}")
        log_result(report, f"Done event status: {status2}")
        
        if attempt_id2 and status2 == "ambiguous":
            # Verify status 1
            att_res2 = requests.get(f"{BASE_URL}/attempt/{attempt_id2}")
            att_data2 = att_res2.json()
            log_result(report, f"Mid-clarification status: {att_data2['status']}, count: {att_data2['clarification_count']}")
            
            # Clarify
            log_result(report, "Submitting clarification: 'Solve for x'")
            clarify_res = requests.post(
                f"{BASE_URL}/solve/clarify",
                json={"attempt_id": attempt_id2, "user_response": "Solve for x"}
            )
            log_result(report, f"Clarify API Response: {clarify_res.status_code}")
            
            # Final check
            time.sleep(2) # Wait for processing
            final_res = requests.get(f"{BASE_URL}/attempt/{attempt_id2}")
            final_data = final_res.json()
            log_result(report, f"Final status: {final_data['status']}, count: {final_data['clarification_count']}")
            if final_data['status'] == "success":
                log_result(report, "Scenario 2: SUCCESS")
            else:
                log_result(report, f"Scenario 2: FAILED (final status={final_data['status']})")
        else:
            log_result(report, f"Scenario 2: FAILED to trigger ambiguity (status={status2})")

        # --- Scenario 3: Exceed clarification cap (cap=2) ---
        log_result(report, "\n--- Scenario 3: Exceed Clarification Cap ---")
        problem3 = "Do it"
        log_result(report, f"Input: {problem3}")
        
        res3 = requests.post(
            f"{BASE_URL}/solve_v3_stream",
            params={"user_id": USER_ID},
            json={
                "confirmed_text": problem3,
                "requested_mode": "minimal",
                "tier": "free",
                "features_used": {}
            },
            stream=True
        )
        
        attempt_id3 = None
        for line in res3.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data = json.loads(line_str[6:])
                    if data.get("type") == "meta":
                        attempt_id3 = data.get("attempt_id")
        
        if attempt_id3:
            # First clarification
            requests.post(f"{BASE_URL}/solve/clarify", json={"attempt_id": attempt_id3, "user_response": "Just do something"})
            time.sleep(1)
            # Second clarification (if ambiguous again)
            att_mid = requests.get(f"{BASE_URL}/attempt/{attempt_id3}").json()
            log_result(report, f"After 1st clarify: status={att_mid['status']}, count={att_mid['clarification_count']}")
            
            if att_mid['status'] == "ambiguous":
                requests.post(f"{BASE_URL}/solve/clarify", json={"attempt_id": attempt_id3, "user_response": "I still don't know"})
                time.sleep(1)
                
                final_res3 = requests.get(f"{BASE_URL}/attempt/{attempt_id3}")
                final_data3 = final_res3.json()
                log_result(report, f"Final result for Cap test: status={final_data3['status']}, count={final_data3['clarification_count']}, failure_code={final_data3.get('failure_code')}")
                
                if final_data3['status'] == "failure" and final_data3.get('failure_code') == "CLARIFICATION_CAP_EXCEEDED":
                    log_result(report, "Scenario 3: SUCCESS")
                else:
                    log_result(report, "Scenario 3: FAILED (expected failure/CLARIFICATION_CAP_EXCEEDED)")
            else:
                log_result(report, f"Scenario 3: FAILED (did not reach 2nd ambiguity, current status={att_mid['status']})")
        else:
            log_result(report, "Scenario 3: FAILED (no attempt_id)")

if __name__ == "__main__":
    run_tests()
