import os
from sqlmodel import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
engine = create_engine(DATABASE_URL)

def add_columns():
    with engine.connect() as conn:
        print("Checking/Adding columns to chatsession table...")
        
        # Check and add learning_mode
        try:
            conn.execute(text("ALTER TABLE chatsession ADD COLUMN learning_mode VARCHAR DEFAULT 'solve'"))
            print("Added learning_mode column")
        except Exception as e:
            print(f"Column learning_mode might already exist: {e}")
            
        # Check and add requested_mode
        try:
            conn.execute(text("ALTER TABLE chatsession ADD COLUMN requested_mode VARCHAR DEFAULT 'minimal'"))
            print("Added requested_mode column")
        except Exception as e:
            print(f"Column requested_mode might already exist: {e}")
            
        # Check and add solve_tier
        try:
            conn.execute(text("ALTER TABLE chatsession ADD COLUMN solve_tier VARCHAR DEFAULT 'free'"))
            print("Added solve_tier column")
        except Exception as e:
            print(f"Column solve_tier might already exist: {e}")
            
        conn.commit()
        print("Done.")

if __name__ == "__main__":
    add_columns()
