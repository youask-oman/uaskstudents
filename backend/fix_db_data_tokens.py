import os
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@postgres:5432/uask_db")
engine = create_engine(DATABASE_URL)

def fix_existing_data():
    print(f"Connecting to {DATABASE_URL}...")
    with engine.connect() as conn:
        # Update tokens_used from NULL to 500 for assistant messages
        try:
            conn.execute(text("UPDATE chatmessage SET tokens_used = 500 WHERE role = 'assistant' AND (tokens_used IS NULL OR tokens_used = 0)"))
            conn.execute(text("UPDATE chatmessage SET model_used = 'OpenAI GPT-4o Mini' WHERE role = 'assistant' AND (model_used IS NULL OR model_used = '')"))
            conn.commit()
            print("Successfully updated existing messages with baseline tokens and model.")
        except Exception as e:
            print(f"Error updating existing data: {e}")
            conn.rollback()

    print("Database data fix complete.")

if __name__ == "__main__":
    fix_existing_data()
