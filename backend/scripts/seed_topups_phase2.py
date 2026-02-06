
from sqlmodel import Session
from app.database import get_session
from app.models import TopUpProduct

PRODUCTS = [
    {"code": "TOPUP_25", "name": "Starter Pack (25 Credits)", "credits": 25, "price_usd": 2.99},
    {"code": "TOPUP_60", "name": "Standard Pack (60 Credits)", "credits": 60, "price_usd": 5.99},
    {"code": "TOPUP_120", "name": "Value Pack (120 Credits)", "credits": 120, "price_usd": 9.99},
    {"code": "TOPUP_250", "name": "Pro Pack (250 Credits)", "credits": 250, "price_usd": 18.99},
    {"code": "TOPUP_600", "name": "Power User (600 Credits)", "credits": 600, "price_usd": 39.99},
]

def seed_topups():
    print("Seeding TopUp Products...")
    session = next(get_session())
    
    for p_data in PRODUCTS:
        # Check by code (Unique)
        from sqlmodel import select
        existing = session.exec(select(TopUpProduct).where(TopUpProduct.code == p_data["code"])).first()
        
        if not existing:
            p = TopUpProduct(**p_data)
            session.add(p)
            print(f"Created {p_data['code']}")
        else:
            # Update price/credits if changed?
            existing.price_usd = p_data["price_usd"]
            existing.credits = p_data["credits"]
            existing.name = p_data["name"]
            session.add(existing)
            print(f"Updated {p_data['code']}")
            
    session.commit()
    print("Done.")

if __name__ == "__main__":
    seed_topups()
