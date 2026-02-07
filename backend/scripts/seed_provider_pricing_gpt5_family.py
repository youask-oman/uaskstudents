"""
Seed Provider Pricing for GPT-5 Family

This script:
1. Retires all non-OpenAI and non-GPT-5* pricing entries
2. Seeds gpt-5-mini as the ONLY ACTIVE pricing
3. Seeds gpt-5 and gpt-5-nano as INACTIVE (for future use)
4. Sets ALLOW_ADVANCED_MODELS=false in SystemConfig

Run once during deployment or whenever pricing needs to be reset.
"""

import sys
import os
from datetime import datetime
from sqlmodel import Session, select

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import ProviderModelPricing, SystemConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pricing_seed")

# Official OpenAI GPT-5 Family Pricing (USD per 1M tokens)
GPT5_PRICING = {
    "gpt-5-mini": {
        "input_per_1m": 0.25,
        "cached_input_per_1m": 0.025,
        "output_per_1m": 2.00,
        "status": "ACTIVE"  # Production model
    },
    "gpt-5": {
        "input_per_1m": 1.25,
        "cached_input_per_1m": 0.125,
        "output_per_1m": 10.00,
        "status": "INACTIVE"  # Available but not default
    },
    "gpt-5-nano": {
        "input_per_1m": 0.05,
        "cached_input_per_1m": 0.005,
        "output_per_1m": 0.40,
        "status": "INACTIVE"  # Available but not default
    }
}

def retire_non_gpt5_pricing(session: Session):
    """Retire all non-OpenAI and non-GPT-5* pricing entries."""
    now = datetime.utcnow()
    
    # Find all active pricing that is NOT (openai, gpt-5*)
    stmt = select(ProviderModelPricing).where(
        ProviderModelPricing.status == "ACTIVE"
    )
    
    all_active = session.exec(stmt).all()
    retired_count = 0
    
    for pricing in all_active:
        # Keep only OpenAI GPT-5 family
        if pricing.provider.lower() != "openai" or not pricing.model.startswith("gpt-5"):
            logger.info(f"Retiring: {pricing.provider}/{pricing.model} (ID: {pricing.id})")
            pricing.status = "INACTIVE"
            pricing.effective_to = now
            pricing.change_reason = "Retired during GPT-5 family migration"
            session.add(pricing)
            retired_count += 1
    
    session.commit()
    logger.info(f"Retired {retired_count} non-GPT-5 pricing entries")
    return retired_count

def seed_gpt5_pricing(session: Session):
    """Seed GPT-5 family pricing."""
    now = datetime.utcnow()
    seeded_count = 0
    
    for model_name, pricing_data in GPT5_PRICING.items():
        # Check if this exact pricing already exists
        stmt = select(ProviderModelPricing).where(
            ProviderModelPricing.provider == "openai",
            ProviderModelPricing.model == model_name,
            ProviderModelPricing.status == pricing_data["status"]
        )
        existing = session.exec(stmt).first()
        
        if existing:
            # Update if values differ
            needs_update = (
                existing.price_in_per_1m != pricing_data["input_per_1m"] or
                existing.price_out_per_1m != pricing_data["output_per_1m"] or
                existing.price_cached_in_per_1m != pricing_data["cached_input_per_1m"]
            )
            
            if needs_update:
                logger.info(f"Updating existing pricing for {model_name}")
                existing.price_in_per_1m = pricing_data["input_per_1m"]
                existing.price_out_per_1m = pricing_data["output_per_1m"]
                existing.price_cached_in_per_1m = pricing_data["cached_input_per_1m"]
                existing.change_reason = "Updated to official GPT-5 pricing"
                session.add(existing)
                seeded_count += 1
            else:
                logger.info(f"Pricing for {model_name} already correct")
        else:
            # Create new pricing entry
            logger.info(f"Creating new pricing for {model_name} (status: {pricing_data['status']})")
            
            # If ACTIVE, retire any existing ACTIVE for this model
            if pricing_data["status"] == "ACTIVE":
                active_stmt = select(ProviderModelPricing).where(
                    ProviderModelPricing.provider == "openai",
                    ProviderModelPricing.model == model_name,
                    ProviderModelPricing.status == "ACTIVE"
                )
                active_existing = session.exec(active_stmt).all()
                for old_pricing in active_existing:
                    old_pricing.status = "INACTIVE"
                    old_pricing.effective_to = now
                    old_pricing.change_reason = "Replaced by GPT-5 official pricing"
                    session.add(old_pricing)
            
            new_pricing = ProviderModelPricing(
                provider="openai",
                model=model_name,
                price_in_per_1m=pricing_data["input_per_1m"],
                price_out_per_1m=pricing_data["output_per_1m"],
                price_cached_in_per_1m=pricing_data["cached_input_per_1m"],
                currency="USD",
                effective_from=now,
                effective_to=None,
                status=pricing_data["status"],
                created_by=None,  # System seeded
                change_reason="Initial GPT-5 family pricing seed"
            )
            session.add(new_pricing)
            seeded_count += 1
    
    session.commit()
    logger.info(f"Seeded/updated {seeded_count} GPT-5 pricing entries")
    return seeded_count

def set_system_config(session: Session):
    """Set ALLOW_ADVANCED_MODELS flag."""
    # Check if config exists
    config = session.exec(
        select(SystemConfig).where(SystemConfig.key == "ALLOW_ADVANCED_MODELS")
    ).first()
    
    if config:
        if config.value != "false":
            logger.info("Updating ALLOW_ADVANCED_MODELS to false")
            config.value = "false"
            config.updated_at = datetime.utcnow()
            session.add(config)
        else:
            logger.info("ALLOW_ADVANCED_MODELS already set to false")
    else:
        logger.info("Creating ALLOW_ADVANCED_MODELS config")
        config = SystemConfig(
            key="ALLOW_ADVANCED_MODELS",
            value="false",
            description="Allow selection of gpt-5 and gpt-5-nano in addition to gpt-5-mini"
        )
        session.add(config)
    
    session.commit()

def main():
    """Run the seeding process."""
    logger.info("=== GPT-5 FAMILY PRICING SEED ===")
    
    with Session(engine) as session:
        # Step 1: Retire non-GPT-5 pricing
        retired = retire_non_gpt5_pricing(session)
        
        # Step 2: Seed GPT-5 family pricing
        seeded = seed_gpt5_pricing(session)
        
        # Step 3: Set system config
        set_system_config(session)
        
        logger.info("\n=== SUMMARY ===")
        logger.info(f"Retired entries: {retired}")
        logger.info(f"Seeded/updated entries: {seeded}")
        logger.info(f"Active model: gpt-5-mini ONLY")
        logger.info(f"Inactive models: gpt-5, gpt-5-nano (available for future use)")
        
        # Verify active pricing
        active_pricing = session.exec(
            select(ProviderModelPricing).where(
                ProviderModelPricing.status == "ACTIVE"
            )
        ).all()
        
        logger.info(f"\nACTIVE PRICING ENTRIES ({len(active_pricing)}):")
        for p in active_pricing:
            logger.info(f"  - {p.provider}/{p.model}: ${p.price_in_per_1m}/1M in, ${p.price_out_per_1m}/1M out")
        
        if len(active_pricing) == 1 and active_pricing[0].model == "gpt-5-mini":
            logger.info("\n✓ SUCCESS: Only gpt-5-mini is active")
        else:
            logger.warning(f"\n⚠ WARNING: Expected 1 active entry (gpt-5-mini), found {len(active_pricing)}")

if __name__ == "__main__":
    main()
