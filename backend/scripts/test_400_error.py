import requests
import json

# Test the solve endpoint with a simple problem
url = "http://localhost:8000/api/v1/solve"

payload = {
    "confirmed_markdown": "What is 5 + 3?",
    "mode": "general",
    "user_id": 1
}

headers = {
    "Content-Type": "application/json"
}

print("Testing solve endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\nSending request...\n")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=90)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 400:
        print(f"\n❌ 400 ERROR DETAILS:")
        print(response.text)
    else:
        print(f"Response: {json.dumps(response.json(), indent=2)[:500]}")
        
except requests.exceptions.Timeout:
    print("\n❌ Request timed out after 90 seconds!")
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
