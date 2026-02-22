
import requests
import json
import time

def test_solve():
    url = "http://localhost:9000/api/v1/solve"
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": "8",
        "X-Request-ID": f"test-e2e-{int(time.time())}"
    }
    
    payload = {
        "text_query": "Differentiate the function f(x) = sin(x^2) with respect to x.",
        "mode": "general",
        "tier": "standard",
        "requested_mode": "minimal"
    }
    
    print(f"Sending solve request to {url}...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Solve successful!")
            print(f"Session ID: {data.get('session_id')}")
            print(f"Model Used: {data.get('model_used')}")
            
            solution = data.get("solution", {})
            problem = solution.get("problem", {})
            print(f"Goal: {problem.get('goal')}")
            
            steps = solution.get("steps", [])
            print(f"Number of steps: {len(steps)}")
            for i, step in enumerate(steps[:2]):
                print(f"Step {i+1}: {step.get('title')}")
                
            final_answer = solution.get("final_answer", {})
            print(f"Final Answer: {final_answer.get('value')}")
            
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_solve()
