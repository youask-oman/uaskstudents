"""
Script to update all users with proper subscription tiers.
Assigns a random tier from [free, student_standard, family_standard] to each user.
Creates Subscription records if missing.
"""

import sys
import os
import random
from datetime import datetime, timedelta
from sqlmodel import Session, select

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import User, Subscription, Plan

def main():
    print("=" * 60)
    print("USER SUBSCRIPTION UPDATE SCRIPT")
    print("=" * 60)
    
    with Session(engine) as session:
        # 1. Get all plans
        plans = session.exec(select(Plan)).all()
        plan_map = {p.slug: p for p in plans}
        
        print(f"\nAvailable Plans: {list(plan_map.keys())}")
        
        if not plans:
            print("ERROR: No plans found in database. Run seed_db.py first.")
            return
        
        # 2. Get all users
        users = session.exec(select(User)).all()
        print(f"Total Users: {len(users)}")
        
        if not users:
            print("No users found. Creating sample users...")
            create_sample_users(session, plan_map)
            return
        
        # 3. Update each user
        tier_distribution = {"free": 0, "student_standard": 0, "family_standard": 0}
        
        for user in users:
            # Skip admin users - they don't need subscriptions
            if user.role == "admin":
                print(f"  [{user.id}] {user.email} - ADMIN (skipped)")
                continue
            
            # Check if user already has a valid subscription
            existing_sub = session.exec(
                select(Subscription).where(Subscription.user_id == user.id)
            ).first()
            
            if existing_sub:
                # Verify subscription points to valid plan
                plan = session.get(Plan, existing_sub.plan_id)
                if plan:
                    user.subscription_tier = plan.slug
                    tier_distribution[plan.slug] = tier_distribution.get(plan.slug, 0) + 1
                    print(f"  [{user.id}] {user.email} - EXISTING: {plan.slug}")
                    session.add(user)
                    continue
            
            # Assign random tier (weighted: 60% free, 25% standard, 15% family)
            roll = random.random()
            if roll < 0.60:
                tier_slug = "free"
            elif roll < 0.85:
                tier_slug = "student_standard"
            else:
                tier_slug = "family_standard"
            
            plan = plan_map.get(tier_slug)
            if not plan:
                print(f"  [{user.id}] {user.email} - ERROR: Plan '{tier_slug}' not found!")
                continue
            
            # Create Subscription
            now = datetime.utcnow()
            sub = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                credits_balance=float(plan.credits_per_month),
                credits_used_this_period=0.0,
                feature_usage={},
                auto_renew=True
            )
            session.add(sub)
            
            # Update user tier
            user.subscription_tier = tier_slug
            user.subscription_status = "active"
            session.add(user)
            
            tier_distribution[tier_slug] = tier_distribution.get(tier_slug, 0) + 1
            print(f"  [{user.id}] {user.email} - ASSIGNED: {tier_slug} ({plan.credits_per_month} credits)")
        
        session.commit()
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for tier, count in tier_distribution.items():
            print(f"  {tier}: {count} users")
        print("=" * 60)
        print("DONE!")


def create_sample_users(session, plan_map):
    """Create sample users for testing if none exist."""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    sample_users = [
        {"email": "student1@test.com", "full_name": "Alice Student", "tier": "free"},
        {"email": "student2@test.com", "full_name": "Bob Learner", "tier": "student_standard"},
        {"email": "student3@test.com", "full_name": "Charlie Scholar", "tier": "family_standard"},
        {"email": "student4@test.com", "full_name": "Diana Free", "tier": "free"},
        {"email": "student5@test.com", "full_name": "Eve Premium", "tier": "student_standard"},
    ]
    
    now = datetime.utcnow()
    
    for data in sample_users:
        user = User(
            email=data["email"],
            full_name=data["full_name"],
            password_hash=pwd_context.hash("testpassword123"),
            role="student",
            subscription_tier=data["tier"],
            subscription_status="active"
        )
        session.add(user)
        session.flush()  # Get ID
        
        plan = plan_map.get(data["tier"])
        if plan:
            sub = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                credits_balance=float(plan.credits_per_month),
                credits_used_this_period=0.0,
                feature_usage={},
                auto_renew=True
            )
            session.add(sub)
        
        print(f"  Created: {data['email']} ({data['tier']})")
    
    session.commit()
    print("\nSample users created successfully!")


if __name__ == "__main__":
    main()
