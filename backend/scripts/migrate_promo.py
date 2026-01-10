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
            # Create 'promocode' table
            print("Creating 'promocode' table...")
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS promocode (
                        id SERIAL PRIMARY KEY,
                        code VARCHAR NOT NULL UNIQUE,
                        discount_percent INTEGER DEFAULT 0,
                        valid_from TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
                        valid_until TIMESTAMP WITHOUT TIME ZONE,
                        is_active BOOLEAN DEFAULT TRUE,
                        max_uses INTEGER,
                        current_uses INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_promocode_code ON promocode (code)"))
                print(" - Created promocode table")
            except Exception as e:
                print(f" - Failed to create promocode table: {e}")
            
            # Seed a default code
            try:
                conn.execute(text("INSERT INTO promocode (code, discount_percent, max_uses) VALUES ('WELCOME20', 20, 100) ON CONFLICT (code) DO NOTHING"))
                print(" - Seeded WELCOME20 code")
            except Exception as e:
                print(f" - Failed to seed code: {e}")

            conn.commit()
            print("Migration completed successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    run_migration()
