import sys
import os
from sqlmodel import SQLModel, create_engine, select, Session

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import Invoice, InvoiceLineItem, InvoiceSequence

def migrate():
    print("Starting Phase 5 Migration (Invoices)...")
    SQLModel.metadata.create_all(engine)
    print("Tables created successfully.")
    
    # Initialize sequence for current year if missing
    from datetime import datetime
    year = datetime.utcnow().year
    
    with Session(engine) as session:
        seq = session.exec(select(InvoiceSequence).where(InvoiceSequence.year == year)).first()
        if not seq:
            print(f"Initializing InvoiceSequence for {year}...")
            session.add(InvoiceSequence(year=year, last_value=0))
            session.commit()
            print("Done.")
        else:
            print(f"InvoiceSequence for {year} already exists.")

if __name__ == "__main__":
    migrate()
