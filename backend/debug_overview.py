
from app.database import engine
from sqlmodel import Session, select, func
from app.models import BillingLedger, CreditLot, RequestEvent
from datetime import datetime, timedelta
import traceback

def test_overview():
    try:
        with Session(engine) as session:
            range_days = 7
            now = datetime.utcnow()
            start_date = now - timedelta(days=range_days)
            
            # 1. Cost
            events = session.exec(select(RequestEvent).where(RequestEvent.created_at >= start_date)).all()
            total_provider_cost = sum([e.cost_usd or 0.0 for e in events])
            print(f"Cost: {total_provider_cost}")
            
            # 2. Credits
            usage_query = select(func.sum(BillingLedger.credits_charged)).where(
                BillingLedger.created_at >= start_date,
                BillingLedger.status.in_(["SETTLED", "CHARGED"])
            )
            print("Running usage query...")
            total_credits_consumed = session.exec(usage_query).one() or 0.0
            print(f"Credits: {total_credits_consumed}")
            
            # 3. Revenue
            topup_revenue_query = select(func.sum(CreditLot.amount_paid)).where(
                CreditLot.purchased_at >= start_date,
                CreditLot.lot_type == "TOPUP"
            )
            total_revenue_usd = session.exec(topup_revenue_query).one() or 0.0
            print(f"Revenue: {total_revenue_usd}")
            
    except Exception as e:
        print("FAIL")
        traceback.print_exc()

if __name__ == "__main__":
    test_overview()
