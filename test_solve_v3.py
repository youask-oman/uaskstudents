import requests
import json
import sys

def test_solve():
    url = "http://localhost:8000/api/v1/solve_v3?user_id=1"
    headers = {"Content-Type": "application/json"}
    payload = {
        "confirmed_text": "Solve 2x + 5 = 15",
        "subject": "mathematics",
        "mode": "general",
        "difficulty": "standard"
    }

    print(f"Testing URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"\nStatus Code: {response.status_code}")
        
        try:
            data = response.json()
            print(f"Response Body: {json.dumps(data, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_solve()
