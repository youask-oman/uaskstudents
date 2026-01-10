"""
Test script to verify login endpoint is working
"""
import requests
import json

def test_login():
    url = "http://localhost:8000/api/v1/login"
    
    payload = {
        "email": "student@uask.ai",
        "password": "student123"
    }
    
    print(f"Testing login endpoint: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Login successful!")
        else:
            print("\n❌ Login failed!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test_login()
