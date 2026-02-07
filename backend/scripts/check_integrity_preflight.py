import sys
import os
from sqlalchemy import func
from sqlmodel import Session, select

# Adjust path to import from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import BillingLedger, Payment, StripeEvent, RequestEvent, Invoice

def check_duplicates():
    with Session(engine) as session:
        # BillingLedger
        bl_dupes = session.exec(
            select(BillingLedger.request_id, func.count('*'))
            .where(BillingLedger.request_id != None)
            .group_by(BillingLedger.request_id)
            .having(func.count('*') > 1)
        ).all()
        print(f"BillingLedger request_id duplicates: {len(bl_dupes)}")
        for r_id, count in bl_dupes[:5]:
            print(f"  - {r_id}: {count}")

        # Payment
        p_dupes = session.exec(
            select(Payment.external_id, func.count('*'))
            .where(Payment.external_id != None)
            .group_by(Payment.external_id)
            .having(func.count('*') > 1)
        ).all()
        print(f"Payment external_id duplicates: {len(p_dupes)}")
        for e_id, count in p_dupes[:5]:
            print(f"  - {e_id}: {count}")

        # StripeEvent
        s_dupes = session.exec(
            select(StripeEvent.stripe_event_id, func.count('*'))
            .where(StripeEvent.stripe_event_id != None)
            .group_by(StripeEvent.stripe_event_id)
            .having(func.count('*') > 1)
        ).all()
        print(f"StripeEvent stripe_event_id duplicates: {len(s_dupes)}")
        
        # Invoice
        i_dupes = session.exec(
            select(Invoice.invoice_number, func.count('*'))
            .where(Invoice.invoice_number != None)
            .group_by(Invoice.invoice_number)
            .having(func.count('*') > 1)
        ).all()
        print(f"Invoice invoice_number duplicates: {len(i_dupes)}")

if __name__ == "__main__":
    check_duplicates()
