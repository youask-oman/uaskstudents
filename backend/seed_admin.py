from app.database import engine, get_session
from app.models import User
from app.auth import get_password_hash
from sqlmodel import Session, select
import datetime

def seed_admin():
    with Session(engine) as session:
        # Check if admin already exists
        statement = select(User).where(User.email == "loai@uask.ai")
        admin = session.exec(statement).first()
        
        if not admin:
            admin = User(
                full_name="Loai Admin",
                email="loai@uask.ai",
                password_hash=get_password_hash("ssLr1980"),
                role="admin",
                subscription_tier="enterprise",
                subscription_status="active",
                quota_questions_total=9999,
                quota_scans_total=9999,
                created_at=datetime.datetime.utcnow(),
                last_active_at=datetime.datetime.utcnow()
            )
            session.add(admin)
            session.commit()
            print("Admin user created: loai@uask.ai")
        else:
            # Update role and password just in case
            admin.role = "admin"
            admin.password_hash = get_password_hash("ssLr1980")
            session.add(admin)
            session.commit()
            print("Admin user updated: loai@uask.ai")

if __name__ == "__main__":
    seed_admin()
