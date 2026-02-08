import os
import requests
import json
from sqlalchemy import inspect, text, create_engine
from sqlmodel import Session

# Load .env manually to avoid dependency issues if python-dotenv is missing
def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

load_env_file("e:/uaskstudents/.env")

# Pre-flight data collection
results = []
results.append("=== PHASE 0: PRE-FLIGHT CHECKS ===")

# A) Environment variables
vlm_model = os.environ.get("VLM_MODEL_OCR", "NOT SET")
results.append(f"VLM_MODEL_OCR={vlm_model}")
openai_key = "EXISTS" if os.environ.get("OPENAI_API_KEY") else "NOT SET"
results.append(f"OPENAI_API_KEY={openai_key}")

# C) Health
try:
    health_res = requests.get("http://localhost:8000/health")
    results.append(f"Health Status Code (/health): {health_res.status_code}")
except Exception as e:
    results.append(f"Health Check Failed: {e}")

# B) DB Schema
db_url = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
results.append(f"Using DATABASE_URL: {db_url}")

try:
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    table_name = 'solveroutputattempt'
    tables = inspector.get_table_names()
    results.append(f"Tables in DB: {tables}")

    if table_name in tables:
        columns = inspector.get_columns(table_name)
        col_names = [c["name"] for c in columns]
        results.append(f"DB Columns for {table_name}:")
        for c in columns:
            results.append(f"  - {c['name']}: {c['type']}")
        
        required_cols = ["attempt_id", "status", "failure_code", "clarification_count", "clarification_history"]
        for rc in required_cols:
            if rc in col_names:
                results.append(f"CHECK: {rc} exists")
            else:
                results.append(f"MISSING: {rc}")
                
        with Session(engine) as session:
            count = session.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
            results.append(f"Current Row Count in {table_name}: {count}")
    else:
        results.append(f"ERROR: Table {table_name} NOT FOUND in DB")

except Exception as e:
    results.append(f"DB Schema Check Failed: {e}")

output_text = "\n".join(results)
print(output_text)

with open("pre_flight_results.txt", "w") as f:
    f.write(output_text)
