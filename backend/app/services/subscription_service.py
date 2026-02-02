from sqlmodel import Session, select, func
from fastapi import HTTPException
from datetime import datetime
from typing import Optional, Tuple
import json

from app.models import User, Plan, Subscription, UsageLedger
from app.schemas.pricing import PlanMultipliers, PlanFeatures, CreditsConfig, SolveCreditsConfig, TierPricingConfig, VerifyCreditsConfig

class SubscriptionService:
    def ensure_plans_exist(self, session: Session):
        """Initialize default plans if they don't exist."""
        count = session.exec(select(func.count(Plan.id))).one()
        if count == 0:
            # Create default plans using new Pydantic schemas for features/multipliers
            
            # 1. Free Plan
            free_feats = PlanFeatures(
                allow_research=False,
                ocr_monthly_cap=3,
                voice_monthly_cap=3,
                daily_credit_cap=5
            )
            free_mults = PlanMultipliers(
                credits=CreditsConfig(
                    solve=SolveCreditsConfig(
                        free=TierPricingConfig(text=1, snap_image=2, snap_pdf=3, voice=2),
                        # Standard/Research are expensive on Free plan
                        standard=TierPricingConfig(text=1000, snap_image=1000, snap_pdf=1000, voice=1000),
                        research=TierPricingConfig(text=1000, snap_image=1000, snap_pdf=1000, voice=1000)
                    )
                )
            )
            free_plan = Plan(
                name="Free", slug="free", credits_per_month=50,
                price_monthly_cents=0, price_yearly_cents=0, seats=1,
                features=free_feats.model_dump(),
                multipliers=free_mults.model_dump(),
                is_active=True
            )
            
            # 2. Student Plan
            student_feats = PlanFeatures(
                allow_research=True,
                ocr_monthly_cap=100,
                voice_monthly_cap=50,
                daily_credit_cap=50
            )
            student_mults = PlanMultipliers(
                credits=CreditsConfig(
                    solve=SolveCreditsConfig(
                        # Free Tier usage for Students
                        free=TierPricingConfig(text=1, snap_image=2, snap_pdf=3, voice=2),
                        # Standard Tier usage for Students
                        standard=TierPricingConfig(text=2, snap_image=3, snap_pdf=4, voice=3),
                        # Research Tier usage for Students
                        research=TierPricingConfig(text=4, snap_image=5, snap_pdf=6, voice=5)
                    )
                )
            )
            student_plan = Plan(
                name="Student Standard", slug="student_standard", credits_per_month=300,
                price_monthly_cents=999, price_yearly_cents=9900, seats=1,
                features=student_feats.model_dump(),
                multipliers=student_mults.model_dump(),
                is_active=True
            )
            
            # 3. Family Plan
            family_feats = PlanFeatures(
                allow_research=True,
                ocr_monthly_cap=200,
                voice_monthly_cap=100,
                daily_credit_cap=100
            )
            # Use same multipliers as Student
            family_plan = Plan(
                name="Family Standard", slug="family_standard", credits_per_month=600,
                price_monthly_cents=1999, price_yearly_cents=19900, seats=3,
                features=family_feats.model_dump(),
                multipliers=student_mults.model_dump(), # Same pricing structure
                is_active=True
            )
            
            session.add(free_plan)
            session.add(student_plan)
            session.add(family_plan)
            session.commit()

    def get_or_create_subscription(self, session: Session, user: User) -> Subscription:
        if user.subscription:
            plan = session.get(Plan, user.subscription.plan_id)
            if plan:
                return user.subscription

            # Repair missing plan reference using the user's tier mapping.
            plan_slug = "free"
            if user.subscription_tier == "pro":
                plan_slug = "student_standard"
            elif user.subscription_tier == "family":
                plan_slug = "family_standard"

            plan = session.exec(select(Plan).where(Plan.slug == plan_slug)).first()
            if not plan:
                self.ensure_plans_exist(session)
                plan = session.exec(select(Plan).where(Plan.slug == plan_slug)).first()
            if not plan:
                raise ValueError("Plan not available for subscription repair")

            user.subscription.plan_id = plan.id
            session.add(user.subscription)
            session.commit()
            session.refresh(user.subscription)
            return user.subscription
        
        # Determine plan based on user.subscription_tier (legacy support)
        plan_slug = "free"
        if user.subscription_tier == "pro":
            plan_slug = "student_standard"
        elif user.subscription_tier == "family":
            plan_slug = "family_standard"
            
        plan = session.exec(select(Plan).where(Plan.slug == plan_slug)).first()
        if not plan:
            plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
            if not plan:
                # Should have been created by ensure_plans_exist, but redundancy is safe
                self.ensure_plans_exist(session)
                plan = session.exec(select(Plan).where(Plan.slug == "free")).first()

        # Calculate period end (1 month from now)
        # In a real app, this would align with billing period
        from datetime import timedelta
        end_date = datetime.utcnow() + timedelta(days=30)
        
        new_sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            current_period_end=end_date,
            credits_balance=float(plan.credits_per_month),
            credits_used_this_period=0,
            feature_usage={}
        )
        session.add(new_sub)
        session.commit()
        session.refresh(new_sub)
        session.refresh(user) # Refresh user to load relation
        return new_sub

    def calculate_cost(self, plan: Plan, tier: str, source_type: str = "text") -> float:
        """
        Calculate cost for a solve action based on Tier and Source Type.
        tier: "free", "standard", "research"
        source_type: "text", "snap_image", "snap_pdf", "voice"
        """
        multipliers_data = plan.multipliers or {}
        
        # Parse into Pydantic model for validation/access
        # If version missing, this might fail unless we migrated. 
        # (Migration script assumed run)
        try:
            mults = PlanMultipliers(**multipliers_data)
        except Exception:
            # Fallback for unmigrated data (safety)
            return 1000.0 

        # 1. Get Tier Config
        tier_config = getattr(mults.credits.solve, tier, None)
        if not tier_config:
            # Invalid tier?
            return 1000.0
            
        # 2. Get Cost by Source Type
        cost = 1
        if source_type == "snap_image":
            cost = tier_config.snap_image
        elif source_type == "snap_pdf":
            cost = tier_config.snap_pdf
        elif source_type == "voice":
            cost = tier_config.voice
        else:
            cost = tier_config.text
            
        return float(cost)

    def check_entitlement_and_debit(
        self, 
        session: Session, 
        user_id: int, 
        action_request: dict
    ) -> dict:
        """
        Check if user can perform action and debit credits.
        action_request: {
            "tier": "free" | "standard" | "research" (optional, derived from mode if missing),
            "mode": "minimal" | "detailed" | "research" (frontend mode),
            "has_ocr": bool,
            "has_voice": bool,
            "source_type": "text" | "snap_image" | "snap_pdf" | "voice" (optional),
            "reference_id": str (optional idempotency key)
        }
        """
        # 0. Idempotency Check
        ref_id = action_request.get("reference_id")
        if ref_id:
             existing = session.exec(select(UsageLedger).where(UsageLedger.reference_id == ref_id)).first()
             if existing:
                 # Already processed
                 user = session.get(User, user_id)
                 if user and user.subscription:
                     return {
                         "allowed": True, 
                         "cost": existing.amount, 
                         "subscription": user.subscription,
                         "new_feature_usage": user.subscription.feature_usage,
                         "meta": existing.meta,
                         "status": "already_processed"
                     }
        
        user = session.get(User, user_id)
        if not user:
             return {"allowed": False, "reason": "User not found"}
            
        subscription = self.get_or_create_subscription(session, user)
        if subscription.status != "active":
             return {"allowed": False, "reason": "Subscription not active"}
             
        plan = subscription.plan
        
        # 1. Parse Features
        features_data = plan.features or {}
        try:
            feats = PlanFeatures(**features_data)
        except:
             # Fallback
             feats = PlanFeatures()
        
        feature_usage = subscription.feature_usage or {}
        
        # 2. Determine Tier & Source
        tier = action_request.get("tier")
        if not tier:
            # Legacy mapping from mode
            mode = action_request.get("mode", "minimal")
            if mode == "detailed":
                tier = "standard"
            elif mode == "research":
                tier = "research"
            else:
                tier = "free"
        
        source = action_request.get("source_type")
        if not source:
            if action_request.get("has_voice"):
                source = "voice"
            elif action_request.get("has_ocr"):
                # TODO: Differentiate snap_image vs snap_pdf if needed
                source = "snap_image"
            else:
                source = "text"

        # 3. Check Gates
        if tier == "research" and not feats.allow_research:
            return {"allowed": False, "reason": "Research tier not included in your plan", "error_code": "TIER_NOT_ALLOWED"}
            
        if tier == "standard":
             # Implicit gate?
             pass

        # 4. Check Caps
        if source in ["snap_image", "snap_pdf"] and feats.ocr_monthly_cap > 0:
            if feature_usage.get("ocr", 0) >= feats.ocr_monthly_cap:
                 return {"allowed": False, "reason": "OCR monthly limit reached", "error_code": "CAP_EXCEEDED", "cap": "ocr_monthly"}
                 
        if source == "voice" and feats.voice_monthly_cap > 0:
            if feature_usage.get("voice", 0) >= feats.voice_monthly_cap:
                 return {"allowed": False, "reason": "Voice monthly limit reached", "error_code": "CAP_EXCEEDED", "cap": "voice_monthly"}

        # Daily Cap Check
        if feats.daily_credit_cap > 0:
             # Calculate usage for today
             start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
             # UsageLedger links to subscription, which links to user.
             # Query by subscription_id for simpler index usage? Or user_id if ledger has it?
             # SubscriptionService usage ledger has subscription_id.
             daily_used = session.exec(
                 select(func.sum(UsageLedger.amount))
                 .where(UsageLedger.subscription_id == subscription.id)
                 .where(UsageLedger.created_at >= start_of_day)
                 .where(UsageLedger.transaction_type == "DEBIT") # Only count debits
             ).one() or 0.0
             
             # Estimate cost of this request?
             # We haven't calculated `cost` variable yet in this function (it's below at step 5).
             # We can pre-calculate cost or check strictly strictly strict?
             # Let's peek cost.
             peek_cost = self.calculate_cost(plan, tier, source)
             if (daily_used + peek_cost) > feats.daily_credit_cap:
                  return {"allowed": False, "reason": "Daily credit limit reached", "error_code": "CAP_EXCEEDED", "cap": "daily_credits"}


        # 5. Calculate Cost
        is_make_it_right = action_request.get("is_make_it_right", False)
        cost = 0.0
        
        if is_make_it_right:
             if feature_usage.get("make_it_right", 0) >= feats.make_it_right_monthly_cap:
                 # Cap exceeded, charge normal price
                 cost = self.calculate_cost(plan, tier, source)
             else:
                 cost = 0.0
        else:
             cost = self.calculate_cost(plan, tier, source)

        # 6. Check Balance
        if subscription.credits_balance < cost:
            return {"allowed": False, "reason": "Insufficient credits", "shortfall": cost - subscription.credits_balance, "error_code": "INSUFFICIENT_CREDITS"}

        # 7. Return entitlement (Caller must execute debit)
        return {
            "allowed": True, 
            "cost": cost, 
            "subscription": subscription,
            "new_feature_usage": feature_usage,
            "meta": {
                "tier": tier,
                "source": source,
                "is_make_it_right": is_make_it_right
            }
        }

    def execute_debit(self, session: Session, subscription: Subscription, cost: float, meta: dict, ref_id: str):
        """
        Actually deduuct credits and log to ledger.
        """
        subscription.credits_balance -= cost
        subscription.credits_used_this_period += cost
        
        # Update feature counters if needed
        fs = dict(subscription.feature_usage or {})
        if meta.get("has_ocr"):
            fs["ocr"] = fs.get("ocr", 0) + 1
        if meta.get("has_voice"):
            fs["voice"] = fs.get("voice", 0) + 1
        if meta.get("is_make_it_right") and cost == 0:
            fs["make_it_right"] = fs.get("make_it_right", 0) + 1
            
        subscription.feature_usage = fs
        session.add(subscription)
        
        ledger = UsageLedger(
            subscription_id=subscription.id,
            transaction_type="DEBIT",
            amount=cost,
            balance_after=subscription.credits_balance,
            reference_id=ref_id,
            meta=meta
        )
        session.add(ledger)
        return ledger

    def refund_credits(self, session: Session, subscription_id: int, amount: float, reason: str, ref_id: str):
        sub = session.get(Subscription, subscription_id)
        if sub:
            sub.credits_balance += amount
            sub.credits_used_this_period -= amount # Revert usage stats? Maybe just refund balance.
            session.add(sub)
            
            ledger = UsageLedger(
                subscription_id=sub.id,
                transaction_type="REFUND",
                amount=amount,
                balance_after=sub.credits_balance,
                reference_id=ref_id,
                meta={"reason": reason}
            )
            session.add(ledger)
            session.commit()

    def charge_for_solve(self, session: Session, user_id: int, mode: str, has_ocr: bool, has_voice: bool, ref_id: str, is_make_it_right: bool = False) -> dict:
        """
        High-level wrapper to check entitlement and execute debit immediately.
        Used by non-streaming solver.
        """
        action_req = {
            "mode": mode,
            "has_ocr": has_ocr, 
            "has_voice": has_voice,
            "is_make_it_right": is_make_it_right
        }
        
        entitlement = self.check_entitlement_and_debit(session, user_id, action_req)
        if not entitlement["allowed"]:
             return entitlement
             
        # Execute
        self.execute_debit(
            session, 
            entitlement["subscription"], 
            entitlement["cost"], 
            action_req, 
            ref_id
        )
        # Add debit_result keys for caller convenience
        entitlement["amount"] = entitlement["cost"]
        entitlement["status"] = "debited"
        return entitlement

    def deduct_credits(self, session: Session, user_id: int, amount: float, reason: str, ref_id: str, meta: dict = None):
        """
        Legacy/Direct wrapper for generic deductions outside the solve loop.
        """
        user = session.get(User, user_id)
        if not user or not user.subscription:
             return
        
        sub = user.subscription
        # Create a dummy meta if not provided
        if not meta: meta = {"reason": reason}
        
        self.execute_debit(session, sub, amount, meta, ref_id)
        return type('DebitResult', (object,), {"amount": amount, "status": "debited"})()

subscription_service = SubscriptionService()
