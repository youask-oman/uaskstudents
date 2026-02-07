import sys
import os
from sqlalchemy import inspect

# Adjust path to import from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine

def check_columns():
    inst = inspect(engine)
    columns = [c['name'] for c in inst.get_columns('requestevent')]
    print("Columns in requestevent table:")
    print(columns)

if __name__ == "__main__":
    check_columns()
