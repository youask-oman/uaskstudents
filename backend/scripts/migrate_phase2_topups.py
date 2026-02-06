from sqlmodel import Session, create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
engine = create_engine(DATABASE_URL)

def run_migration():
    print("Running Phase 2 Migration...")
    with Session(engine) as session:
        # 1. Update CreditLot
        # SQLite needs table recreation for extensive schema changes usually, but we try ALTER per column.
        # Check if lot_type exists
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN lot_type VARCHAR DEFAULT 'TOPUP'"))
            print("Added lot_type")
        except Exception: pass
        
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN subscription_id INTEGER REFERENCES subscription(id)"))
            print("Added subscription_id")
        except Exception: pass
        
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN status VARCHAR DEFAULT 'ACTIVE'"))
            print("Added status")
        except Exception: pass
        
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN external_ref VARCHAR"))
            print("Added external_ref")
        except Exception: pass
        
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN currency VARCHAR DEFAULT 'USD'"))
            print("Added currency")
        except Exception: pass
        
        try:
            session.connection().execute(text("ALTER TABLE creditlot ADD COLUMN amount_paid FLOAT"))
            print("Added amount_paid")
        except Exception: pass
        
        # 2. Add New Tables
        # Use SQLModel to create tables ensuring dialect compatibility
        # Imports are needed so they are registered in metadata
        from sqlmodel import SQLModel
        from app.models import CreditLotConsumption, TopUpProduct, CreditLot
        
        print("Creating tables via SQLModel...")
        SQLModel.metadata.create_all(engine)
        
        session.commit()
    print("Phase 2 Migration Complete")

if __name__ == "__main__":
    run_migration()
