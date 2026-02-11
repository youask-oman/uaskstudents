from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import ChatMessage, ChatSession, User
from app.auth import get_password_hash
from scripts.seed_production import run_seed


def _auth_header(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/api/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_or_create_student() -> User:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "student_edit_mode@example.com")).first()
        if user:
            return user
        user = User(
            email="student_edit_mode@example.com",
            full_name="Student Edit Mode",
            password_hash=get_password_hash("DevOnlyChangeMe123!"),
            role="student",
            is_internal=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _create_chat_session(user_id: int) -> int:
    with Session(engine) as session:
        chat = ChatSession(
            user_id=user_id,
            title="Edit Mode Test",
            subject="Math",
            is_saved=True,
        )
        session.add(chat)
        session.commit()
        session.refresh(chat)
        sample_solution = {
            "topic": "Algebra",
            "steps": [
                {"k": 1, "title": "Isolate x", "body_markdown": "Subtract 7: $2x = 12$."},
                {"k": 2, "title": "Solve", "body_markdown": "Divide by 2: $x = 6$."},
            ],
            "final_answer": {"text": "x = 6", "latex": "x = 6"},
        }
        session.add(ChatMessage(session_id=chat.id, role="user", content="Solve for x: 2x + 7 = 19"))
        session.add(
            ChatMessage(
                session_id=chat.id,
                role="assistant",
                content="Assistant",
                structured_data=sample_solution,
                telemetry={"channel": "canvas_primary"},
            )
        )
        session.commit()
        return chat.id


def test_edit_mode_notes_and_copy_flow():
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)
    client = TestClient(app)
    student = _get_or_create_student()
    headers = _auth_header(client, student.email, "DevOnlyChangeMe123!")
    session_id = _create_chat_session(student.id)

    # Canonical markdown
    canon_resp = client.get(f"/api/v1/chat/{session_id}/canonical_markdown", headers=headers)
    assert canon_resp.status_code == 200, canon_resp.text
    canon_payload = canon_resp.json()
    assert canon_payload["canonical_md"].strip()
    assert canon_payload["canonical_md_hash"]

    # Notes GET -> empty
    notes_resp = client.get(f"/api/v1/chat/{session_id}/notes", headers=headers)
    assert notes_resp.status_code == 200, notes_resp.text
    assert notes_resp.json()["version"] in (0, 1)

    # Notes PUT
    put_notes = client.put(
        f"/api/v1/chat/{session_id}/notes",
        headers=headers,
        json={"notes_md": "My notes", "expected_version": 0},
    )
    assert put_notes.status_code == 200, put_notes.text
    version = put_notes.json()["version"]

    # Notes conflict
    conflict = client.put(
        f"/api/v1/chat/{session_id}/notes",
        headers=headers,
        json={"notes_md": "Conflict", "expected_version": 0},
    )
    assert conflict.status_code == 409

    # Edit copy auto-create
    edit_resp = client.get(f"/api/v1/chat/{session_id}/edit_copy", headers=headers)
    assert edit_resp.status_code == 200, edit_resp.text
    edit_payload = edit_resp.json()
    assert edit_payload["version"] == 1

    # Edit copy update
    update_resp = client.put(
        f"/api/v1/chat/{session_id}/edit_copy",
        headers=headers,
        json={"edited_md": "Updated copy", "expected_version": edit_payload["version"]},
    )
    assert update_resp.status_code == 200, update_resp.text

    # Reset
    reset_resp = client.post(f"/api/v1/chat/{session_id}/edit_copy/reset", headers=headers)
    assert reset_resp.status_code == 200, reset_resp.text

    # Auth check (other user)
    other_user = User(
        email=f"other_{int(datetime.utcnow().timestamp())}@example.com",
        full_name="Other User",
        password_hash=get_password_hash("DevOnlyChangeMe123!"),
        role="student",
        is_internal=False,
    )
    with Session(engine) as session:
        session.add(other_user)
        session.commit()
        session.refresh(other_user)
    other_headers = _auth_header(client, other_user.email, "DevOnlyChangeMe123!")
    denied = client.get(f"/api/v1/chat/{session_id}/notes", headers=other_headers)
    assert denied.status_code == 403
