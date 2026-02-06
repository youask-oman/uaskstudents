from sqlmodel import Session, select
from app.database import engine
from app.services.provider_pricing_service import provider_pricing_service
from app.models import ProviderModelPricing

def main():
    print("Seeding Phase 0 Pricing Defaults...")
    with Session(engine) as session:
        # Check if already seeded
        existing = session.exec(select(ProviderModelPricing)).first()
        if existing:
            print("Pricing already exists. Skipping.")
            return

        provider_pricing_service.seed_defaults(session)
        print("Seeding complete.")

if __name__ == "__main__":
    main()
