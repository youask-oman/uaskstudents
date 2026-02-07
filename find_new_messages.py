from app.database import engine
from app.models import ChatMessage
from sqlmodel import Session, select
from datetime import datetime, timedelta

def find_new_messages():
    with Session(engine) as session:
        # Messages from the last hour
        since = datetime.utcnow() - timedelta(hours=1)
        messages = session.exec(
            select(ChatMessage).where(ChatMessage.created_at > since).order_by(ChatMessage.id)
        ).all()
        
        print(f"New Messages (since {since}):")
        for m in messages:
            print(f"ID: {m.id}, Session: {m.session_id}, Role: {m.role}, Content: {m.content[:50]}...")

if __name__ == "__main__":
    find_new_messages()
