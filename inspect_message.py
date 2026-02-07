from app.database import engine
from app.models import ChatMessage
from sqlmodel import Session, select
import json

def inspect_message(message_id):
    with Session(engine) as session:
        m = session.get(ChatMessage, message_id)
        if m:
            print(f"ID: {m.id}")
            print(f"Content: {m.content}")
            print(f"Structured Data: {json.dumps(m.structured_data, indent=2)}")
        else:
            print(f"Message {message_id} not found")

if __name__ == "__main__":
    import sys
    mid = int(sys.argv[1]) if len(sys.argv) > 1 else 247
    inspect_message(mid)
