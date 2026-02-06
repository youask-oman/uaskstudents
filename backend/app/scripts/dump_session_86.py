
import logging
import sys
import os
import json
from sqlmodel import Session, select

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.database import engine
from app.models import ChatSession, ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def dump_session(session_id: int):
    output_file = f"E:/uaskstudents/backend/app/session_{session_id}_dump.txt"
    with Session(engine) as session:
        # Check session exists
        chat_session = session.get(ChatSession, session_id)
        if not chat_session:
            print(f"Session {session_id} not found.")
            return

        # Get messages
        statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        messages = session.exec(statement).all()

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Title: {chat_session.title}\n")
            f.write(f"Created At: {chat_session.created_at}\n")
            f.write("-" * 40 + "\n\n")

            for msg in messages:
                f.write(f"[{msg.role.upper()}] ({msg.created_at})\n")
                if msg.content:
                    f.write(f"CONTENT:\n{msg.content}\n")
                if msg.structured_data:
                    f.write(f"STRUCTURED_DATA:\n{json.dumps(msg.structured_data, indent=2)}\n")
                f.write("-" * 40 + "\n\n")
        
        print(f"Dumped session {session_id} to {output_file}")

if __name__ == "__main__":
    dump_session(86)
