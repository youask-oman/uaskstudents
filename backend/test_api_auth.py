
from app.auth import create_access_token
from datetime import timedelta
import requests

email = "loai@uask.ai"
# Token valid for 1 hour
token = create_access_token(data={"sub": email}, expires_delta=timedelta(hours=1))
print(f"Generated Token: {token}")

url = "http://127.0.0.1:8000/api/admin/payments/overview"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
