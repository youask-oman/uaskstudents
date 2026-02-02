"""Debug the subscription endpoint"""
from app.api import build_subscription_response
from app.models import *
from app.database import engine
from sqlmodel import Session, select
import traceback

def _sync_subscription_balance(subscription, plan, session):
    expected_remaining = max(float(plan.credits_per_month) - float(subscription.credits_used_this_period or 0), 0.0)
    if subscription.credits_balance != expected_remaining:
        subscription.credits_balance = expected_remaining
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
    return expected_remaining

with Session(engine) as s:
    u = s.get(User, 1)
    print(f"User: {u}")
    print(f"User's subscription: {u.subscription if u else None}")
    
    try:
        from app.services.subscription_service import subscription_service
        sub = subscription_service.get_or_create_subscription(s, u)
        print(f"Subscription: {sub}")
        
        plan = s.get(Plan, sub.plan_id)
        print(f"Plan: {plan}")
        
        # Test the sync balance
        credits_remaining = _sync_subscription_balance(sub, plan, s)
        print(f"Credits remaining: {credits_remaining}")
        
        # Test build_subscription_response
        resp = build_subscription_response(u, sub, plan, credits_remaining)
        print(f"Response: {resp}")
    except Exception as e:
        traceback.print_exc()
