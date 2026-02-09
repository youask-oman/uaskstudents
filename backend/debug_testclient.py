from fastapi import FastAPI
from fastapi.testclient import TestClient

def test_simple():
    app = FastAPI()
    try:
        client = TestClient(app)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple()
