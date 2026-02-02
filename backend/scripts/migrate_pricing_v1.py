
import sys
import os
from sqlmodel import Session, select, create_engine
from app.models import Plan
from app.schemas.pricing import PlanMultipliers, PlanFeatures, CreditsConfig, SolveCreditsConfig, TierPricingConfig, VerifyCreditsConfig

# Ensure we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database import engine  # Assuming engine is exposed here

def migrate_pricing():
    with Session(engine) as session:
        plans = session.exec(select(Plan)).all()
        print(f"Found {len(plans)} plans to check.")

        for plan in plans:
            print(f"Checking Plan: {plan.name} ({plan.slug})")
            
            # Check if already migrated
            current_mult = plan.multipliers or {}
            if current_mult.get("version", 0) >= 1:
                print(f"  - Already v1+. Skipping.")
                continue

            # --- Migrate Multipliers ---
            # Old keys: text_concise, text_detailed, ocr_add, voice_add
            # New structure: See PlanMultipliers
            
            # Determine base costs from old keys
            # For Free plan: text_concise=1, text_detailed=1000 (disabled)
            # For Student: text_concise=1, text_detailed=2
            
            old_concise = current_mult.get("text_concise", 1)
            old_detailed = current_mult.get("text_detailed", 2)
            
            # Construct Tier Configs
            # We map "Free Tier" actions to the "text_concise" cost (Minimal)
            # We map "Standard Tier" actions to the "text_detailed" cost (Detailed)
            # Research Tier is new, default to 2x Standard or 4
            
            research_cost = old_detailed * 2 if old_detailed < 100 else 4

            # NOTE: In the new system, "Free Tier" refers to the *quality/model tier*, not the User's Plan.
            # A user on Free Plan might be allowed to use Free Tier (cost 1) but not Standard Tier (cost 1000).
            # A user on Student Plan uses Free Tier (cost 1) and Standard Tier (cost 2).
            
            # So, we populate the costs for ALL tiers in EACH plan, based on what that plan *charged* for them.
            
            new_credits = CreditsConfig(
                solve=SolveCreditsConfig(
                    free=TierPricingConfig(
                        text=old_concise,
                        snap_image=old_concise + 1, # Heuristic
                        snap_pdf=old_concise + 2,
                        voice=old_concise + 1
                    ),
                    standard=TierPricingConfig(
                        text=old_detailed,
                        snap_image=old_detailed + 1,
                        snap_pdf=old_detailed + 2,
                        voice=old_detailed + 1
                    ),
                    # Research wasn't in old system, pick reasonable defaults
                    research=TierPricingConfig(
                        text=research_cost,
                        snap_image=research_cost + 1,
                        snap_pdf=research_cost + 2,
                        voice=research_cost + 1
                    )
                ),
                verify=VerifyCreditsConfig(
                    free=1,
                    standard=1,
                    research=2
                ),
                plot_trigger=0,
                plot_spec=1
            )
            
            new_multipliers = PlanMultipliers(
                version=1,
                credits=new_credits
            )
            
            plan.multipliers = new_multipliers.model_dump()
            print(f"  - Migrated multipliers.")

            # --- Migrate Features ---
            current_feat = plan.features or {}
            
            # Determine logic for gates
            allow_research = True
            if "free" in plan.slug.lower():
                allow_research = False
            
            # Preserve existing caps if present
            new_features = PlanFeatures(
                allow_research=current_feat.get("allow_research", allow_research),
                allow_verify=current_feat.get("allow_verify", True),
                allow_plot=current_feat.get("allow_plot", True),
                
                daily_credit_cap=current_feat.get("daily_credit_cap", 50),
                ocr_monthly_cap=current_feat.get("ocr_monthly_cap", 100),
                voice_monthly_cap=current_feat.get("voice_monthly_cap", 50),
                generated_images_monthly_cap=current_feat.get("generated_images_monthly_cap", 20),
                make_it_right_monthly_cap=current_feat.get("make_it_right_monthly_cap", 5)
            )
            
            plan.features = new_features.model_dump()
            print(f"  - Migrated features.")
            
            session.add(plan)
        
        session.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate_pricing()
