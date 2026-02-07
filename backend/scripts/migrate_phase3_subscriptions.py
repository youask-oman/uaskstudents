
import sys
import os
from datetime import datetime

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, SQLModel
from app.database import engine, get_session
from app.models import Subscription, SubscriptionPeriod, CreditLot

def run_migration():
    print("Starting Phase 3 Migration (Subscriptions)...")
    
    # 1. Create Tables
    print("Creating tables via SQLModel...")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Check if any SubscriptionPeriod rows exist
        count = session.exec(select(SubscriptionPeriod)).all()
        print(f"Existing SubscriptionPeriod rows: {len(count)}")
        
        # Optional: Backfill for existing active subscriptions?
        # For now, we will rely on the grant job to pick them up if they don't have periods.
        
        # Verify CreditLot lot_type enum?
        # SQLModel/SQLAlchemy enums are usually just strings in DB unless explicit enum type used.
        # Our model uses str, so it accepts "SUBSCRIPTION_GRANT" without migration.
        
    print("Phase 3 Migration Complete")

if __name__ == "__main__":
    run_migration()
