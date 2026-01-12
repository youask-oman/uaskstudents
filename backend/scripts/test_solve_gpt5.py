import requests
import json

def test_solve():
    url = "http://localhost:8000/api/v1/solve"
    payload = {
        "text_query": "Solve for x: 2x+7=19",
        "mode": "general",
        "user_id": 1
    }
    
    print("Testing /api/v1/solve with GPT-5 mini...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload)
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Session ID: {data.get('session_id')}")
        print(f"Model: {data.get('model_used')}")
        print(f"Final Answer: {data.get('final_answer')}")
        print(f"Steps Count: {len(data.get('steps', []))}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_solve()
