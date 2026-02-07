import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from sqlalchemy import inspect

insp = inspect(engine)
cols = insp.get_columns('providermodelpricing')

print("ProviderModelPricing columns:")
for c in cols:
    print(f"  {c['name']}: {c['type']}")
