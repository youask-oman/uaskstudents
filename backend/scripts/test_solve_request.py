import requests
import json

url = "http://localhost:8000/api/v1/solve"
payload = {
    "text_query": "2x+2=4",
    "mode": "general",
    "user_id": 1
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
