
import sys
import os
from sqlalchemy import text, inspect
from sqlmodel import SQLModel, create_engine

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import StripeEvent, TopUpOrder, SubscriptionBillingLink, StripePriceMap

def run_migration():
    print("Starting Phase 4 Migration...")
    
    # 1. Create New Tables
    # SQLModel.metadata.create_all only creates tables that don't exist
    print("Creating new tables (StripeEvent, TopUpOrder, SubscriptionBillingLink, StripePriceMap)...")
    SQLModel.metadata.create_all(engine)
    
    # 2. Alter Existing Table: Payment
    print("Altering existing table: payment...")
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('payment')]
    
    alter_statements = []
    
    if "subscription_id" not in columns:
        alter_statements.append("ALTER TABLE payment ADD COLUMN subscription_id INTEGER")
    
    if "provider" not in columns:
        alter_statements.append("ALTER TABLE payment ADD COLUMN provider VARCHAR DEFAULT 'STRIPE'")
        
    if "external_id" not in columns:
        alter_statements.append("ALTER TABLE payment ADD COLUMN external_id VARCHAR")
        
    if "external_type" not in columns:
        alter_statements.append("ALTER TABLE payment ADD COLUMN external_type VARCHAR")
        
    if "idempotency_key" not in columns:
        alter_statements.append("ALTER TABLE payment ADD COLUMN idempotency_key VARCHAR")
        
    if "metadata_json" not in columns:
        # SQLite supports JSON, Postgres supports JSONB or JSON
        json_type = "JSONB" if "postgresql" in str(engine.url) else "JSON"
        alter_statements.append(f"ALTER TABLE payment ADD COLUMN metadata_json {json_type}")

    if alter_statements:
        with engine.connect() as conn:
            for stmt in alter_statements:
                try:
                    print(f"Executing: {stmt}")
                    conn.execute(text(stmt))
                    conn.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Failed or already exists: {e}")
                    conn.rollback()
    else:
        print("No alterations needed for payment table.")

    # 3. Add Constraints if possible
    # Note: Adding unique constraints via ALTER TABLE can be tricky on SQLite
    if "postgresql" in str(engine.url):
        try:
            with engine.connect() as conn:
                print("Adding unique constraint uq_payment_external...")
                conn.execute(text("ALTER TABLE payment ADD CONSTRAINT uq_payment_external UNIQUE (provider, external_type, external_id)"))
                conn.commit()
        except Exception as e:
            print(f"Skipping constraint (likely exists): {e}")

    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
