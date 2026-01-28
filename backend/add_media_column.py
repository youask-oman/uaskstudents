from sqlmodel import create_engine, text
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def add_media_column():
    stmt = "ALTER TABLE chatmessage ADD COLUMN media_url VARCHAR"
    try:
        with engine.connect() as conn:
            print(f"Executing: {stmt}")
            conn.execute(text(stmt))
            conn.commit()
            print("Success.")
    except Exception as e:
        print(f"Skipped/Failed (probably exists): {e}")

if __name__ == "__main__":
    add_media_column()
