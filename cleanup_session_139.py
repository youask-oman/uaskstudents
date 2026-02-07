from app.database import engine
from app.models import ChatMessage
from sqlmodel import Session, select, delete
import json

def cleanup_session(session_id, keep_id):
    with Session(engine) as session:
        # Delete messages > keep_id for this session
        statement = delete(ChatMessage).where(ChatMessage.session_id == session_id).where(ChatMessage.id > keep_id)
        result = session.exec(statement)
        session.commit()
        print(f"Deleted {result.rowcount} messages from session {session_id}")

if __name__ == "__main__":
    import sys
    sid = 139
    keep = 245
    cleanup_session(sid, keep)
