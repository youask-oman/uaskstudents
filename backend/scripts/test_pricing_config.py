"""
Test Provider Pricing API and Configuration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from sqlmodel import Session, select
from app.models import ProviderModelPricing, SystemConfig
import json

def test_pricing():
    with Session(engine) as session:
        print("=== PROVIDER PRICING TEST ===\n")
        
        # Test 1: Get all active pricing
        print("1. ACTIVE PRICING:")
        active = session.exec(
            select(ProviderModelPricing).where(
                ProviderModelPricing.status == "ACTIVE"
            )
        ).all()
        
        for p in active:
            print(f"   {p.provider}/{p.model}:")
            print(f"     Input: ${p.price_in_per_1m}/1M")
            print(f"     Cached Input: ${p.price_cached_in_per_1m}/1M")
            print(f"     Output: ${p.price_out_per_1m}/1M")
            print(f"     Status: {p.status}")
            print(f"     Effective: {p.effective_from} -> {p.effective_to or 'current'}")
            print()
        
        # Test 2: Get all GPT-5 family (including inactive)
        print("\n2. ALL GPT-5 FAMILY PRICING:")
        gpt5_all = session.exec(
            select(ProviderModelPricing).where(
                ProviderModelPricing.provider == "openai",
                ProviderModelPricing.model.like("gpt-5%")
            )
        ).all()
        
        for p in gpt5_all:
            print(f"   {p.model}: {p.status}")
        
        # Test 3: Check system config
        print("\n3. SYSTEM CONFIG:")
        config = session.exec(
            select(SystemConfig).where(
                SystemConfig.key == "ALLOW_ADVANCED_MODELS"
            )
        ).first()
        
        if config:
            print(f"   ALLOW_ADVANCED_MODELS = {config.value}")
            print(f"   Description: {config.description}")
        else:
            print("   ALLOW_ADVANCED_MODELS not set")
        
        # Test 4: Verify only gpt-5-mini is active
        print("\n4. VALIDATION:")
        if len(active) == 1 and active[0].model == "gpt-5-mini":
            print("   ✓ Only gpt-5-mini is ACTIVE")
        else:
            print(f"   ✗ Expected 1 active (gpt-5-mini), found {len(active)}")
        
        gpt5_count = len([p for p in gpt5_all if p.model.startswith("gpt-5")])
        if gpt5_count == 3:
            print(f"   ✓ All 3 GPT-5 family models seeded")
        else:
            print(f"   ✗ Expected 3 GPT-5 models, found {gpt5_count}")
        
        inactive_count = len([p for p in gpt5_all if p.status == "INACTIVE" and p.model in ["gpt-5", "gpt-5-nano"]])
        if inactive_count == 2:
            print(f"   ✓ gpt-5 and gpt-5-nano are INACTIVE")
        else:
            print(f"   ✗ Expected 2 inactive advanced models, found {inactive_count}")

if __name__ == "__main__":
    test_pricing()
