
import os
import sys
from sqlmodel import Session, create_engine, select
from sqlalchemy import text
 
# Add current directory to path so we can import app modules
sys.path.append(os.getcwd())

# Setup DB - using the default from database.py if env var not set
# We assume the environment variables are set similarly to the running app, 
# or we use the default which seems to be local postgres.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
engine = create_engine(DATABASE_URL)

def check_session_60():
    with Session(engine) as session:
        # Check ChatSession table first
        print(f"Checking session with ID 60 in {DATABASE_URL}")
        

        # We can use raw SQL to avoid model import issues if models are complex
        # But let's try to query chat_session table directly
        try:
            result = session.exec(text("SELECT * FROM chatsession WHERE id = 60")).mappings().one_or_none()
            if not result:
                print("Session 60 NOT FOUND in database.")
                return
            
            print(f"Found Session 60: Title='{result.get('title')}'")
            
            # Now check messages for this session
            msgs = session.exec(text("SELECT * FROM chatmessage WHERE session_id = 60 ORDER BY id")).mappings().all()
            print(f"Found {len(msgs)} messages for session 60.")
            
            for msg in msgs:
                content = msg.get("content", "")
                structured_data = msg.get("structured_data")
                
                print(f"\nMessage ID {msg.get('id')} Role: {msg.get('role')}")
                if "plot" in str(content).lower() or "graph" in str(content).lower():
                    print("  [TEXT MATCH] Content contains 'plot' or 'graph'")
                
                if structured_data:
                    import json
                    # structured_data might be a dict or string depending on driver/model
                    if isinstance(structured_data, str):
                        try:
                            data = json.loads(structured_data)
                        except:
                            data = {}
                    else:
                        data = structured_data
                        
                    visuals = data.get("visuals", [])
                    print(f"  Structured Data Visuals: {visuals}")
                    
                    if visuals:
                        print("  => HAS PLOT/VISUALS!")
                        for v in visuals:
                             print(f"     - {v}")
                    else:
                        print("  => No visuals in structured_data.")
                        


        except Exception as e:
            print(f"Error querying database: {e}")
            session.rollback()
            try:
                print("Listing all tables in public schema:")
                result = session.exec(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).all()
                for row in result:
                    print(f" - {row}")
            except Exception as e2:
                print(f"Could not list tables: {e2}")

if __name__ == "__main__":
    check_session_60()
