import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"
USER_ID = 11

def verify_scenario_2():
    print("--- Starting Scenario 2 Verification ---")
    
    # 1. Trigger ambiguous solve
    solve_payload = {
        "confirmed_text": "x", # Very ambiguous
        "requested_mode": "minimal",
        "tier": "free",
        "features_used": {}
    }
    
    print(f"Step 1: POST /solve_v3_stream with 'x'...")
    response = requests.post(
        f"{BASE_URL}/solve_v3_stream",
        params={"user_id": USER_ID},
        json=solve_payload,
        stream=True
    )
    
    attempt_id = None
    is_ambiguous = False
    refusal_message = None

    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "meta":
                        print(f"DEBUG Full Meta: {data}")
                        attempt_id = data.get("attempt_id")
                        print(f"Extracted attempt_id: {attempt_id}")
                    if data.get("type") == "done":
                        print(f"DEBUG Done Data: {data}")
                        if data.get("error", {}).get("code") == "ambiguous_response":
                            is_ambiguous = True
                            refusal_message = data["error"].get("refusal") or data["error"].get("message")
                            print(f"Received ambiguous_response error: {refusal_message}")
                except Exception as e:
                    # print(f"DEBUG Parse error: {e}")
                    pass

    if not attempt_id:
        print("FAIL: No attempt_id received")
        return

    if not is_ambiguous:
        print("FAIL: Expected ambiguous status, but did not receive 'ambiguous_response' event")
        return

    # 2. Verify status via GET /attempt/{attempt_id}
    print(f"Step 2: GET /attempt/{attempt_id} after ambiguous signal...")
    status_res = requests.get(f"{BASE_URL}/attempt/{attempt_id}")
    status_data = status_res.json()
    
    print(f"Current Status: {status_data['status']}")
    print(f"Clarification Count: {status_data['clarification_count']}")
    
    if status_data['status'] != "ambiguous":
        print(f"FAIL: Expected status 'ambiguous', got '{status_data['status']}'")
        return
    if status_data['clarification_count'] != 1:
        print(f"FAIL: Expected clarification_count 1, got {status_data['clarification_count']}")
        return

    # 3. Resolve via /solve/clarify
    print("Step 3: POST /solve/clarify with 'Solve for x'...")
    clarify_payload = {
        "attempt_id": attempt_id,
        "user_response": "Solve for x"
    }
    clarify_res = requests.post(f"{BASE_URL}/solve/clarify", json=clarify_payload)
    if clarify_res.status_code != 200:
        print(f"FAIL: /solve/clarify returned {clarify_res.status_code}: {clarify_res.text}")
        return
    
    print("Clarification submitted successfully.")

    # 4. Final verification
    print(f"Step 4: GET /attempt/{attempt_id} after resolution...")
    # Give it a small moment for DB to update if async (though clarified is usually sync in this impl)
    time.sleep(1) 
    final_status_res = requests.get(f"{BASE_URL}/attempt/{attempt_id}")
    final_data = final_status_res.json()
    
    print(f"Final Status: {final_data['status']}")
    print(f"Final Clarification Count: {final_data['clarification_count']}")
    
    if final_data['status'] != "success":
        # Maybe it's still processing?
        if final_data['status'] == "processing":
             print("Status is 'processing', waiting 5 more seconds...")
             time.sleep(5)
             final_data = requests.get(f"{BASE_URL}/attempt/{attempt_id}").json()
             print(f"Final Status (after wait): {final_data['status']}")

    if final_data['status'] == "success":
        print("SUCCESS: Scenario 2 verified end-to-end!")
    else:
        print(f"FAIL: Expected status 'success', got '{final_data['status']}'")

if __name__ == "__main__":
    verify_scenario_2()
