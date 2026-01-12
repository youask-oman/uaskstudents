import requests
import json

# Test the solve endpoint directly
url = "http://localhost:8000/api/v1/solve"

payload = {
    "confirmed_markdown": "2+2",
    "mode": "general"
}

headers = {
    "Content-Type": "application/json",
    "Connection": "close"
}

print("Testing solve endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except requests.exceptions.Timeout:
    print("\nERROR: Request timed out after 60 seconds!")
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
