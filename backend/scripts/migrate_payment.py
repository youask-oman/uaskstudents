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
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN ip_address VARCHAR"))
                print(" - Added ip_address")
            except Exception as e:
                print(f" - ip_address might already exist: {e}")

            try:
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN country VARCHAR"))
                print(" - Added country")
            except Exception as e:
                print(f" - country might already exist: {e}")

            # Create 'payment' table
            print("Creating 'payment' table...")
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS payment (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        amount FLOAT NOT NULL,
                        currency VARCHAR NOT NULL DEFAULT 'USD',
                        status VARCHAR NOT NULL DEFAULT 'pending',
                        transaction_id VARCHAR NOT NULL,
                        payment_method VARCHAR NOT NULL DEFAULT 'card',
                        ip_address VARCHAR,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
                        FOREIGN KEY (user_id) REFERENCES "user" (id)
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payment_transaction_id ON payment (transaction_id)"))
                print(" - Created payment table")
            except Exception as e:
                print(f" - Failed to create payment table: {e}")
            
            conn.commit()
            print("Migration completed successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    run_migration()
