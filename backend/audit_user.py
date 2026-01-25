from sqlmodel import Session, select
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv() 

from app.database import engine
from app.models import User, Subscription, Plan

def dump_user_state():
    with Session(engine) as session:
        print("\n=== [USER STATE AUDIT] ===")
        user = session.get(User, 4)
        if not user:
            print("User ID 4 not found.")
            return
            
        print(f"User: {user.email} (ID: {user.id})")
        print(f"Grade: {user.grade_level}")
        
        if user.subscription:
            sub = user.subscription
            print(f"Subscription Status: {sub.status}")
            plan = session.get(Plan, sub.plan_id)
            print(f"Active Plan: {plan.name if plan else 'None'} (Slug: {plan.slug if plan else 'N/A'})")
        else:
            print("No active subscription found.")
        print("==========================\n")

if __name__ == "__main__":
    dump_user_state()
