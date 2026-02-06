
from sqlmodel import Session, create_engine, text
import os

# Adjust DB URL if needed
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./uaskstudents.db")
# If using Postgres in docker (from earlier context):
# DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

engine = create_engine(DATABASE_URL)

def run_migration():
    print("Running Phase 1 Billing Migration...")
    
    with Session(engine) as session:
        # Check if column exists, if not add it.
        # SQLite doesn't support IF NOT EXISTS in ALTER COLUMN easily, so we catch errors.
        
        # 1. BillingLedger Columns
        billing_columns = [
            ("provider_cost_usd", "FLOAT DEFAULT 0.0"),
            ("markup_multiplier", "FLOAT DEFAULT 1.0"),
            ("fixed_fee_usd", "FLOAT DEFAULT 0.0"),
            ("charge_usd", "FLOAT DEFAULT 0.0"),
            ("credit_value_usd", "FLOAT DEFAULT 0.0"),
            ("tier", "VARCHAR"),
            ("finalized_at", "DATETIME") # TIMESTAMP in PG
        ]
        
        for col_name, col_type in billing_columns:
            try:
                print(f"Adding {col_name} to billingledger...")
                # For SQLite/PG compatibility, simple ALTER ADD is mostly universal 
                # (except SQLite limitation used to extend, but recent versions OK).
                session.connection().execute(text(f"ALTER TABLE billingledger ADD COLUMN {col_name} {col_type}"))
                session.commit()
            except Exception as e:
                print(f"Skipped {col_name}: {e}")
                session.rollback()

        # 2. UsageLedger request_id
        try:
            print("Adding request_id to usageledger...")
            session.connection().execute(text("ALTER TABLE usageledger ADD COLUMN request_id VARCHAR"))
            session.commit()
        except Exception as e:
            print(f"Skipped usageledger.request_id: {e}")
            session.rollback()
            
        # 3. Add Index/Constraint (DB specific)
        # We skip unique constraint here to avoid DB-specific syntax issues in a generic script,
        # but logic enforces it.
        
    print("Migration Complete.")

if __name__ == "__main__":
    run_migration()
