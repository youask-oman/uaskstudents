import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.database import engine
from app.models.credit_program_models import CreditProgramDefinition, CreditProgramEnrollment
from app.models import User, BillingLedger, CreditLot
from sqlmodel import Session, select

def seed():
    with Session(engine) as session:
        # 1. Create Credit Programs
        programs_data = [
            {
                "name": "Standard Beta Gift",
                "slug": "standard_beta_gift",
                "description": "Welcome gift for beta users",
                "status": "active",
                "monthly_gift_credits": 1000.0,
                "gift_expiry_window_days": 30
            },
            {
                "name": "Power User Program",
                "slug": "power_user",
                "description": "High allowance for internal testers",
                "status": "active",
                "monthly_gift_credits": 50000.0,
                "gift_expiry_window_days": 90
            }
        ]

        # Get a valid admin user ID
        admin_user = session.exec(select(User)).first()
        admin_id = admin_user.id if admin_user else None

        for p_data in programs_data:
            existing = session.exec(select(CreditProgramDefinition).where(CreditProgramDefinition.slug == p_data["slug"])).first()
            if not existing:
                program = CreditProgramDefinition(
                    name=p_data["name"],
                    slug=p_data["slug"],
                    description=p_data["description"],
                    status=p_data["status"],
                    monthly_gift_credits=Decimal(str(p_data["monthly_gift_credits"])),
                    gift_expiry_window_days=p_data["gift_expiry_window_days"],
                    effective_from=datetime.utcnow(),
                    created_by=admin_id
                )
                session.add(program)
                print(f"Created program: {program.slug}")
        
        session.commit()

        # 2. Enroll first few users if they exist
        users = session.exec(select(User).limit(5)).all()
        program = session.exec(select(CreditProgramDefinition).where(CreditProgramDefinition.slug == "standard_beta_gift")).first()
        
        if users and program:
            for user in users:
                existing = session.exec(
                    select(CreditProgramEnrollment)
                    .where(CreditProgramEnrollment.user_id == user.id)
                    .where(CreditProgramEnrollment.program_id == program.id)
                ).first()
                
                if not existing:
                    enrollment = CreditProgramEnrollment(
                        user_id=user.id,
                        program_id=program.id,
                        status="active",
                        started_at=datetime.utcnow()
                    )
                    session.add(enrollment)
                    print(f"Enrolled user {user.email} into {program.slug}")

                    # Give them a starting lot
                    lot = CreditLot(
                        user_id=user.id,
                        lot_type="GIFT",
                        credits_total=Decimal("1000.0"),
                        credits_remaining=Decimal("1000.0"),
                        source=f"Program: {program.slug}",
                        expires_at=datetime.utcnow() + timedelta(days=30)
                    )
                    session.add(lot)
                    
                    # Update User Balance
                    user.credits_balance = (user.credits_balance or Decimal("0")) + Decimal("1000.0")
                    session.add(user)

                    # Ledger entry
                    credits_before = (user.credits_balance or Decimal("0")) - Decimal("1000.0")
                    ledger = BillingLedger(
                        user_id=user.id,
                        action_type="credit_grant",
                        status="SETTLED",
                        credits_charged=Decimal("-1000.0"), # Negative charge = credit
                        credits_before=credits_before,
                        credits_after=user.credits_balance,
                        idempotency_key=f"seed_grant_{user.id}_{datetime.utcnow().timestamp()}"
                    )
                    session.add(ledger)
            
            session.commit()
            print("Seeding complete.")
        else:
            print("No users found to enroll.")

if __name__ == "__main__":
    seed()
