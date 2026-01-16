from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@uask_postgres:5432/uask_db")
engine = create_engine(DATABASE_URL)

def run_migration():
    print("Migrating Database...")
    with engine.connect() as conn:
        try:
            # Check if column exists strictly (though IF NOT EXISTS handles it usually, distinct per dialect)
            # Postgres supports IF NOT EXISTS for ADD COLUMN in recent versions
            conn.execute(text("ALTER TABLE chatmessage ADD COLUMN IF NOT EXISTS telemetry JSON;"))
            conn.commit()
            print("✅ Added 'telemetry' column to 'chatmessage' table.")
        except Exception as e:
            print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    run_migration()
