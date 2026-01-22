from sqlmodel import Session, select, func
from fastapi import HTTPException
from datetime import datetime
from typing import Optional, Tuple
import json

from app.models import User, Plan, Subscription, UsageLedger

class SubscriptionService:
    def ensure_plans_exist(self, session: Session):
        """Initialize default plans if they don't exist."""
        count = session.exec(select(func.count(Plan.id))).one()
        if count == 0:
            free_plan = Plan(
                name="Free",
                slug="free",
                credits_per_month=50,
                price_monthly_cents=0,
                price_yearly_cents=0,
                seats=1,
                features={
                    "ocr_monthly_cap": 3,
                    "voice_monthly_cap": 3,
                    "generated_images_monthly_cap": 5,
                    "daily_credit_cap": 5,
                    "make_it_right_monthly_cap": 5
                },
                multipliers={
                    "text_concise": 1,
                    "text_detailed": 1000, # Effectively disabled or requires upgrade
                    "ocr_add": 1,
                    "voice_add": 1
                },
                is_active=True
            )
            
            student_plan = Plan(
                name="Student Standard",
                slug="student_standard",
                credits_per_month=300,
                price_monthly_cents=999,
                price_yearly_cents=9900,
                seats=1,
                features={
                    "ocr_monthly_cap": 100,
                    "voice_monthly_cap": 50,
                    "generated_images_monthly_cap": 20,
                    "daily_credit_cap": 50,
                    "make_it_right_monthly_cap": 20
                },
                multipliers={
                    "text_concise": 1,
                    "text_detailed": 2,
                    "ocr_add": 1,
                    "voice_add": 1
                },
                is_active=True
            )
            
            family_plan = Plan(
                name="Family Standard",
                slug="family_standard",
                credits_per_month=600,
                price_monthly_cents=1999,
                price_yearly_cents=19900,
                seats=3,
                features={
                    "ocr_monthly_cap": 200,
                    "voice_monthly_cap": 100,
                    "generated_images_monthly_cap": 50,
                    "daily_credit_cap": 100,
                    "make_it_right_monthly_cap": 50
                },
                multipliers={
                    "text_concise": 1,
                    "text_detailed": 2,
                    "ocr_add": 1,
                    "voice_add": 1
                },
                is_active=True
            )
            
            session.add(free_plan)
            session.add(student_plan)
            session.add(family_plan)
            session.commit()

    def get_or_create_subscription(self, session: Session, user: User) -> Subscription:
        if user.subscription:
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

    def calculate_cost(self, plan: Plan, mode: str, has_ocr: bool, has_voice: bool) -> float:
        multipliers = plan.multipliers or {}
        base_cost = multipliers.get(f"text_{mode}", 1) 
        
        # Check if mode is effectively disabled (high cost)
        if base_cost >= 999:
             # Logic to handle disabled can be here, or check features['allowed_modes']
             # For now, we trust the cost reflects it.
             pass

        cost = base_cost
        if has_ocr:
            cost += multipliers.get("ocr_add", 1)
        if has_voice:
            cost += multipliers.get("voice_add", 1)
            
        return float(cost)

    def check_entitlement_and_debit(
        self, 
        session: Session, 
        user_id: int, 
        action_request: dict
    ) -> dict:
        """
        Check if user can perform action and debit credits tentatively.
        action_request: {
            "mode": "concise" | "detailed",
            "has_ocr": bool,
            "has_voice": bool,
            "question_hash": str,
            "is_make_it_right": bool
        }
        Returns: {"allowed": bool, "cost": float, "reason": str, "subscription_id": int}
        """
        user = session.get(User, user_id)
        if not user:
             return {"allowed": False, "reason": "User not found"}
            
        subscription = self.get_or_create_subscription(session, user)
        if subscription.status != "active":
             return {"allowed": False, "reason": "Subscription not active"}
             
        plan = subscription.plan
        
        # 1. Check Feature Caps
        caps = plan.features or {}
        feature_usage = subscription.feature_usage or {}
        
        if action_request.get("has_ocr"):
            if feature_usage.get("ocr", 0) >= caps.get("ocr_monthly_cap", 0) and caps.get("ocr_monthly_cap", 0) > 0:
                return {"allowed": False, "reason": "OCR monthly limit reached"}
        
        if action_request.get("has_voice"):
             if feature_usage.get("voice", 0) >= caps.get("voice_monthly_cap", 0) and caps.get("voice_monthly_cap", 0) > 0:
                return {"allowed": False, "reason": "Voice monthly limit reached"}

        # 2. Daily Cap Check (Optional, simplified)
        # Need to query ledger for today's usage if strict, or use redis. 
        # Skipping strict daily cap for MVP to avoid expensive query, user requested optional.

        # 3. Calculate Cost
        if action_request.get("is_make_it_right", False):
            # Verify if eligible for free Make it Right
            # Logic: Check if we have already given a free Make it Right for this question hash
            # This is complex in a single transaction. 
            # Simplified: Assume allowed if passed here, controller checks eligibility logic or trusting flag if internal.
            # But we must check if they have Make It Right credits left in plan?
            if feature_usage.get("make_it_right", 0) >= caps.get("make_it_right_monthly_cap", 5):
                 # Fallback to normal cost if cap exceeded
                 cost = self.calculate_cost(plan, action_request["mode"], action_request["has_ocr"], action_request["has_voice"])
            else:
                 cost = 0.0
        else:
            cost = self.calculate_cost(plan, action_request["mode"], action_request["has_ocr"], action_request["has_voice"])

        # 4. Check Balance
        if subscription.credits_balance < cost:
            return {"allowed": False, "reason": "Insufficient credits", "shortfall": cost - subscription.credits_balance}

        # 5. Debit (Locking row would be ideal here in a transaction block)
        # Using simple decrement for now - optimistic locking or db-level atomic update is safer
        # subscription.credits_balance -= cost -- handled by caller commit? 
        # Better to return plan/cost and let caller finalize in transaction
        
        return {
            "allowed": True, 
            "cost": cost, 
            "subscription": subscription,
            "new_feature_usage": feature_usage # Helper to update counters
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

subscription_service = SubscriptionService()
