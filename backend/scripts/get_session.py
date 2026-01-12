import requests
import json
import time

def get_session_details(session_id):
    url = f"http://localhost:8000/api/v1/sessions/{session_id}"
    print(f"Fetching session {session_id} from {url}...")
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2))
        else:
            print("Error Response:")
            print(response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

import sys

if __name__ == "__main__":
    session_id = sys.argv[1] if len(sys.argv) > 1 else 8
    get_session_details(session_id)
