import requests

def test_requests_endpoint():
    # Attempt to hit the endpoint locally
    # Note: We need a token. Since we are on the same machine, we can try to find one or just see if it's 401 or 500.
    url = "http://localhost:8000/api/admin/payments/requests"
    try:
        r = requests.get(url)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 500:
            print("Response:", r.text)
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    test_requests_endpoint()
