from sqlmodel import Session, select, create_engine
from app.models import User
from app.auth import get_password_hash
from app.database import engine

def seed_users():
    with Session(engine) as session:
        # Check if test user exists
        user = session.exec(select(User).where(User.email == "final@uask.ai")).first()
        
        hashed_pwd = get_password_hash("password")
        
        if not user:
            print("Creating test user...")
            user = User(
                email="final@uask.ai",
                full_name="Final Verify",
                password_hash=hashed_pwd,
                role="student",
                is_verified=True
            )
            session.add(user)
        else:
            print("Updating test user password...")
            user.password_hash = hashed_pwd
            user.is_verified = True
            session.add(user)
            
        session.commit()
        print("User seeded successfully: final@uask.ai / password")

if __name__ == "__main__":
    seed_users()
