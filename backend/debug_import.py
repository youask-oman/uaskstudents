
import time
import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

print("Starting import diagnostics...")

t_start = time.time()

print("1. Importing app.models...")
t0 = time.time()
try:
    from app.models import User, BillingLedger
    print(f"   [OK] app.models imported in {time.time()-t0:.4f}s")
except Exception as e:
    print(f"   [FAIL] app.models import failed: {e}")

print("2. Importing app.services.pricing_service...")
t0 = time.time()
try:
    from app.services.pricing_service import pricing_service
    print(f"   [OK] pricing_service imported in {time.time()-t0:.4f}s")
except Exception as e:
    print(f"   [FAIL] pricing_service import failed: {e}")

print("3. Importing app.services.billing_service...")
t0 = time.time()
try:
    from app.services.billing_service import billing_service
    print(f"   [OK] billing_service imported in {time.time()-t0:.4f}s")
except Exception as e:
    print(f"   [FAIL] billing_service import failed: {e}")

print("4. Creating SQLModel Engine (SQLite)...")
t0 = time.time()
try:
    from sqlmodel import create_engine, SQLModel
    from sqlmodel.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    print(f"   [OK] Engine created in {time.time()-t0:.4f}s")
    
    print("5. Creating Tables (metadata.create_all)...")
    t1 = time.time()
    SQLModel.metadata.create_all(engine)
    print(f"   [OK] Tables created in {time.time()-t1:.4f}s")
except Exception as e:
    print(f"   [FAIL] DB setup failed: {e}")

print(f"Total time: {time.time()-t_start:.4f}s")
