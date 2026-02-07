
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from sqlalchemy import inspect

def inspect_schema():
    insp = inspect(engine)
    
    tables = ['systemerrorentry', 'billingledger', 'creditlot', 'providermodelpricing']
    
    print("=== SCHEMA INSPECTION ===")
    for table in tables:
        if insp.has_table(table):
            print(f"\nTable: {table}")
            cols = insp.get_columns(table)
            for c in cols:
                print(f"  {c['name']}: {c['type']}")
        else:
            print(f"\nTable: {table} DOES NOT EXIST")

if __name__ == "__main__":
    inspect_schema()
