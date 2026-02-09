import sys
from pathlib import Path
from sqlmodel import Session, select

# Add backend to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.models import User
from app.auth import get_password_hash

def rehash_all_passwords(new_password: str):
    print(f"Hashing new password: {new_password}...")
    new_hash = get_password_hash(new_password)
    
    with Session(engine) as session:
        statement = select(User)
        users = session.exec(statement).all()
        
        print(f"Updating {len(users)} users...")
        for user in users:
            user.password_hash = new_hash
            session.add(user)
        
        session.commit()
    print("All user passwords updated successfully.")

if __name__ == "__main__":
    rehash_all_passwords("admin1234")
