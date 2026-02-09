from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()

try:
    client = TestClient(app)
    print("TestClient(app) - OK")
except Exception as e:
    print(f"TestClient(app) - FAIL: {e}")
    try:
        client = TestClient(transport=None, app=app, base_url="http://test")
        print("TestClient(app=app) - OK")
    except Exception as e2:
         print(f"TestClient(app=app) - FAIL: {e2}")
