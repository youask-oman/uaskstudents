import sys
import os
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.database import engine
from app.models import User
from sqlmodel import Session, select

with Session(engine) as session:
    users = session.exec(select(User).limit(5)).all()
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}")
