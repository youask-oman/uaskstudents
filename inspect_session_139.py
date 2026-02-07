from app.database import engine
from app.models import ChatMessage
from sqlmodel import Session, select
import json

def inspect_session(session_id):
    with Session(engine) as session:
        messages = session.exec(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
        ).all()
        
        print(f"Messages for Session {session_id}:")
        for m in messages:
            print(f"ID: {m.id}, Role: {m.role}")
            print(f"Content: {m.content[:200]}...")
            if m.structured_data:
                print(f"Structured Data: {json.dumps(m.structured_data, indent=2)[:500]}...")
            print("-" * 40)

if __name__ == "__main__":
    inspect_session(139)
