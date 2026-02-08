from sqlmodel import Session, select
from app.database import engine
from app.models import ChatMessage
import sys
import json

def fetch_message_data():
    try:
        with Session(engine) as session:
            # Query for the specific message
            stmt = select(ChatMessage).where(ChatMessage.session_id == 234).where(ChatMessage.id == 398)
            message = session.exec(stmt).first()
            
            if not message:
                print("Message not found (session_id=234, id=398).")
                return

            print(f"--- Message ID: {message.id} ---")
            print(f"Role: {message.role}")
            print(f"Content Preview: {message.content[:200] if message.content else 'None'}")
            
            # Print structured data as raw JSON dump
            if message.structured_data:
                print("\n--- Structured Data (Raw Dump) ---")
                print(json.dumps(message.structured_data, indent=2))
            else:
                print("\n--- No Structured Data ---")

    except Exception as e:
        print(f"Error fetching message: {e}")

if __name__ == "__main__":
    fetch_message_data()
