
import sys
from pathlib import Path
from sqlmodel import Session, select, text

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.models import User
from app.auth import get_password_hash

def main():
    print("Patching internal users...")
    with Session(engine) as session:
        # Find users with uask.ai email
        users = session.exec(select(User).where(User.email.like("%@uask.ai"))).all()
        count = 0
        for user in users:
            changed = False
            if not user.is_internal:
                user.is_internal = True
                changed = True
            
            valid_roles = {"admin", "employee", "superadmin"}
            if user.role not in valid_roles:
                user.role = "employee"
                changed = True
            
            if user.email == "admin@uask.ai":
                 # Reset password to known dev default
                 new_hash = get_password_hash("DevOnlyChangeMe123!")
                 if user.password_hash != new_hash:
                     user.password_hash = new_hash
                     changed = True
                     print("Reset admin password.")
            
            if changed:
                session.add(user)
                count += 1
        
        # Also, if we can't find them via ORM (if is_internal didn't exist before, maybe ORM filters failed?)
        # But now column exists.
        
        # Safe fallback: raw SQL
        session.exec(text("UPDATE \"user\" SET is_internal = true WHERE email LIKE '%@uask.ai'"))
        session.commit()
        
        print(f"Patched users with @uask.ai to is_internal=True.")

if __name__ == "__main__":
    main()
