from app.database import engine
from sqlalchemy import text

def inspect():
    with engine.connect() as conn:
        print("--- prompttemplate ---")
        res = conn.execute(text("SELECT * FROM prompttemplate"))
        print(res.fetchall())
        
        print("\n--- promptversion ---")
        res = conn.execute(text("SELECT * FROM promptversion"))
        print(res.fetchall())

if __name__ == "__main__":
    inspect()
