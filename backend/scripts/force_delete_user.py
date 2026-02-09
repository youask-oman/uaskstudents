import sys
from pathlib import Path
from sqlmodel import Session, select, text

# Add backend to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.models import User

def force_delete_user(user_id: int):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            print(f"User {user_id} not found.")
            return
        
        print(f"Deleting user {user_id} ({user.email})...")
        
        # Tables to clear. Using lowercase as seen in DB inspect.
        tables = [
            "usagelog", "chatsession", "creditlotconsumption", "creditprogramgrantlog",
            "creditprogramenrollment", "reconciliationrecord", "creditlot", "billingledger",
            "ocrjob", "voicesession", "solvesession", "userquotaoverride",
            "devicesignuplog", "subscription", "adminnote", "payment",
            "usersavedsolution", "ocrauditevent", "adminauditlog",
            "solveroutputattempt"
        ]
        
        for table in tables:
            try:
                col = "admin_user_id" if table == "adminauditlog" else "user_id"
                res = session.execute(text(f"DELETE FROM {table} WHERE {col} = :uid"), {"uid": user_id})
                print(f"  Deleted {res.rowcount} from {table}")
            except Exception as e:
                # print(f"  Skip {table}: {e}")
                pass
        
        try:
            session.delete(user)
            session.commit()
            print("User deleted successfully.")
        except Exception as e:
            print(f"FAILED to delete user: {e}")
            session.rollback()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        force_delete_user(int(sys.argv[1]))
    else:
        print("Usage: python force_delete_user.py <user_id>")
