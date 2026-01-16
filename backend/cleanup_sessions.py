import sys
import os

# Add the current directory to sys.path so we can import app modules
sys.path.append(os.getcwd())

from sqlmodel import Session, select, col
from app.database import engine
from app.models import ChatSession, ChatMessage

def cleanup():
    with Session(engine) as session:
        # 1. Delete Error Sessions
        print("Scanning for Error sessions...")
        # Note: SQLModel/SQLAlchemy startswith
        statement = select(ChatSession).where(ChatSession.title.like("Error%"))
        errors = session.exec(statement).all()
        
        count_errors = len(errors)
        for e in errors:
            print(f"Deleting Error Session {e.id}: {e.title}")
            # Delete messages first
            msgs = session.exec(select(ChatMessage).where(ChatMessage.session_id == e.id)).all()
            for m in msgs:
                session.delete(m)
            session.delete(e)
        session.commit()
        print(f"Deleted {count_errors} error sessions.")
        
        # 2. Delete Duplicates
        print("Scanning for Duplicates...")
        
        query = select(ChatSession).order_by(ChatSession.user_id, ChatSession.created_at.desc())
        all_sessions = session.exec(query).all()
        
        seen_keys = set()
        to_delete = []
        
        for s in all_sessions:
            if s.user_id is None:
                continue
                
            key = (s.user_id, s.title)
            
            if key in seen_keys:
                to_delete.append(s)
            else:
                seen_keys.add(key)
        
        count_dupes = len(to_delete)
        for s in to_delete:
            print(f"Deleting Duplicate Session {s.id} (User {s.user_id}): {s.title}")
            # Delete messages first
            msgs = session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id)).all()
            for m in msgs:
                session.delete(m)
            session.delete(s)
            
        session.commit()
        print(f"Deleted {count_dupes} duplicate sessions.")
        print("Cleanup Complete.")

if __name__ == "__main__":
    cleanup()
