
import sys
import os
from datetime import datetime

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.database import engine
from app.models import Plan

def seed_plans():
    print("Seeding Phase 3 Plans...")
    with Session(engine) as session:
        # Define Phase 3 Specs
        plans_data = [
            {
                "slug": "free",
                "name": "Free Tier",
                "credits": 20,
                "price": 0,
                "features": {
                    "monthly_credits_included": 20,
                    "overage_policy": "block",
                    "spend_order": "allowance_first",
                    "monthly_limits": {"ocr": 5, "voice": 0},
                    "allow_verify": False,
                    "allow_plot": False
                }
            },
            {
                "slug": "standard",
                "name": "Standard Helper",
                "credits": 300,
                "price": 999, # $9.99
                "features": {
                    "monthly_credits_included": 300,
                    "overage_policy": "paygo",
                    "spend_order": "allowance_first",
                    "monthly_limits": {"ocr": 100, "voice": 100},
                    "allow_verify": True,
                    "allow_plot": True
                }
            },
            {
                "slug": "research",
                "name": "Research Pro",
                "credits": 800,
                "price": 1999, # $19.99
                "features": {
                    "monthly_credits_included": 800,
                    "overage_policy": "paygo",
                    "spend_order": "allowance_first",
                    "monthly_limits": {"ocr": 1000, "voice": 1000},
                    "allow_verify": True,
                    "allow_plot": True
                }
            }
        ]
        
        for p_data in plans_data:
            plan = session.exec(select(Plan).where(Plan.slug == p_data["slug"])).first()
            if not plan:
                print(f"Creating Plan: {p_data['slug']}")
                plan = Plan(
                    slug=p_data["slug"],
                    name=p_data["name"],
                    credits_per_month=p_data["credits"],
                    price_monthly_cents=p_data["price"],
                    price_yearly_cents=p_data["price"] * 10,
                    features=p_data["features"],
                    multipliers={} # Inherit defaults or set specific
                )
                session.add(plan)
            else:
                print(f"Updating Plan: {p_data['slug']}")
                # Merge new features into old
                current_features = plan.features or {}
                current_features.update(p_data["features"])
                plan.features = current_features
                session.add(plan)
        
        session.commit()
    print("Seeding Complete.")

if __name__ == "__main__":
    seed_plans()
