import requests
import json

try:
    response = requests.get("http://localhost:8000/api/v1/sessions/117")
    data = response.json()
    with open("session_117_clean.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Saved to session_117_clean.json")
except Exception as e:
    print(f"Error: {e}")
