import sys
import os

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text
from app.database import engine

def run_migration():
    with engine.connect() as conn:
        conn.begin()
        try:
            # Add columns to 'user' table
            print("Migrating 'user' table...")
            try:
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN tokens_used_this_month INTEGER DEFAULT 0"))
                print(" - Added tokens_used_this_month")
            except Exception as e:
                print(f" - tokens_used_this_month might already exist: {e}")

            try:
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN last_token_reset TIMESTAMP WITHOUT TIME ZONE DEFAULT now()"))
                print(" - Added last_token_reset")
            except Exception as e:
                print(f" - last_token_reset might already exist: {e}")

            # Add columns to 'chatsession' table
            print("Migrating 'chatsession' table...")
            try:
                conn.execute(text("ALTER TABLE \"chatsession\" ADD COLUMN is_saved BOOLEAN DEFAULT FALSE"))
                print(" - Added is_saved")
            except Exception as e:
                print(f" - is_saved might already exist: {e}")
            
            conn.commit()
            print("Migration completed successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    run_migration()
