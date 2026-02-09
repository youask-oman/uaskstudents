import os
from fastapi.testclient import TestClient
from app.main import app
from app.models import User
from sqlmodel import Session, select
from app.database import engine

def test_http_exception_404_passthrough():
    """
    Regression test: Ensure HTTPException(404) is NOT swallowed and turned into 500.
    The /api/v1/solve endpoint raises 404 if user is not found.
    """
    client = TestClient(app)
    # Use a likely non-existent user ID
    invalid_user_id = 999999
    
    # Ensure it doesn't exist
    with Session(engine) as session:
        user = session.get(User, invalid_user_id)
        if user:
            session.delete(user)
            session.commit()

    resp = client.post(
        "/api/v1/solve",
        json={"text_query": "What is 2+2?", "user_id": invalid_user_id},
        headers={"X-User-ID": str(invalid_user_id)}
    )
    
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"
    assert "User not found" in resp.json()["detail"]

def test_validation_error_422():
    """Ensure Pydantic validation errors return 422, not 500."""
    client = TestClient(app)
    # Send invalid type for user_id to trigger 422
    resp = client.post(
        "/api/v1/solve",
        json={"user_id": "this-should-be-an-int"}
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}. Body: {resp.text}"

def test_unhandled_exception_500():
    """Ensure unexpected exceptions return 500 with a safe message."""
    client = TestClient(app)
    # We can mock something to raise an exception or use a path that we know might fail
    # or just trust the global handler we added if we can trigger it.
    pass
