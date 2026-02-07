
from app.database import engine
from app.models import BillingLedger
from sqlalchemy import inspect, text
from sqlmodel import Session

def sync_billing_ledger():
    inspector = inspect(engine)
    existing_columns = [c['name'] for c in inspector.get_columns('billingledger')]
    
    # Define columns to add with their types (SQLite compatible)
    # Using simple mapping for SQLite: float -> REAL, int -> INTEGER, dict -> JSON, datetime -> DATETIME
    columns_to_add = [
        ("status", "VARCHAR DEFAULT 'SETTLED'"),
        ("estimated_credits", "REAL DEFAULT 0.0"),
        ("actual_credits", "REAL DEFAULT 0.0"),
        ("delta_credits", "REAL DEFAULT 0.0"),
        ("fee_tokens_applied", "INTEGER DEFAULT 0"),
        ("estimated_usage_json", "JSON"),
        ("actual_usage_json", "JSON"),
        ("config_version_id", "INTEGER"),
        ("provider_cost_usd", "REAL DEFAULT 0.0"),
        ("markup_multiplier", "REAL DEFAULT 1.0"),
        ("fixed_fee_usd", "REAL DEFAULT 0.0"),
        ("charge_usd", "REAL DEFAULT 0.0"),
        ("credit_value_usd", "REAL DEFAULT 0.0"),
        ("tier", "VARCHAR"),
        ("finalized_at", "DATETIME"),
        ("updated_at", "DATETIME"),
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    stmt = f"ALTER TABLE billingledger ADD COLUMN {col_name} {col_type}"
                    print(f"Executing: {stmt}")
                    conn.execute(text(stmt))
                    conn.commit()
                    print(f"Added column: {col_name}")
                except Exception as e:
                    print(f"Failed to add {col_name}: {e}")
            else:
                print(f"Column {col_name} already exists.")

if __name__ == "__main__":
    sync_billing_ledger()
