import requests
import json
import time
import sys

def test_solve_33_plus_9():
    url = "http://localhost:8000/api/v1/solve"
    
    # Payload for 33+9 (Text Only)
    payload = {
        "text_query": "33+9",
        "mode": "general"
    }
    
    print(f"--- STARTING WORKFLOW VERIFICATION ---")
    print(f"Target: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload)
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n--- API RESPONSE ({duration:.2f}s) ---")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n[SUCCESS] Response JSON:")
            print(json.dumps(data, indent=2))
            
            # Validation
            solution = data.get("solution", {})
            final_answer = solution.get("final_answer", "")
            steps = solution.get("steps", [])
            
            print("\n--- VALIDATION ---")
            print(f"Final Answer: {final_answer}")
            print(f"Steps count: {len(steps)}")
            
            if "42" in final_answer:
                print("✅ Correct answer '42' found in final_answer.")
            else:
                print("❌ Answer '42' NOT found in final_answer.")
                
        else:
            print("\n[FAILURE] Error Response:")
            print(response.text)

    except Exception as e:
        print(f"\n[EXCEPTION] Request failed: {e}")

if __name__ == "__main__":
    test_solve_33_plus_9()
