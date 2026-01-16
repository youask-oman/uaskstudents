import sys
import os
from sqlalchemy import create_engine, text
from sqlmodel import Session
import json

def check_session(session_id):
    db_url = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@postgres:5432/uask_db")
    engine = create_engine(db_url)
    
    with Session(engine) as db:
        result = db.execute(text("SELECT structured_data, tokens_used, telemetry FROM chatmessage WHERE session_id = :sid AND role = 'assistant'"), {"sid": session_id}).first()
        if result:
            sd = result[0]
            print(f"Tokens: {result[1]}")
            print(f"Telemetry: {result[2]}")
            if sd:
                print(f"Keys: {list(sd.keys())}")
                print(f"Steps count: {len(sd.get('steps', []))}")
                print(f"Final answer: {sd.get('final_answer', {}).get('answer_text', 'N/A')[:100]}")
                print(f"Truncated: {sd.get('_truncated', False)}")
                print(f"Error: {sd.get('error', 'None')}")
            else:
                print("No structured_data")
        else:
            print("No assistant message found")

if __name__ == "__main__":
    sid = int(sys.argv[1]) if len(sys.argv) > 1 else 133
    check_session(sid)
