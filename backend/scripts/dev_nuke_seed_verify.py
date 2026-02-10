import argparse
import subprocess
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine

def run_command(cmd, cwd=None):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd)
    if res.returncode != 0:
        print(f"Command failed with code {res.returncode}")
        print("Aborting workflow.")
        sys.exit(res.returncode)

def nuke_db():
    print("Nuking Database (Truncating data tables)...")
    with engine.connect() as conn:
        # Get all table names
        result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = [row[0] for row in result]
        
        tables_to_truncate = [t for t in tables if t != "alembic_version"]
        if tables_to_truncate:
             quoted = [f"\"{t}\"" for t in tables_to_truncate]
             cmd = f"TRUNCATE TABLE {', '.join(quoted)} CASCADE;"
             print(f"Truncating {len(tables_to_truncate)} tables...")
             conn.execute(text(cmd))
             conn.commit()
    print("Database Nuked (Data only). Schema preserved.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", help="Confirmation token", required=True)
    args = parser.parse_args()
    
    app_env = os.environ.get("APP_ENV", "DEV")
    if app_env != "DEV":
        print(f"Safety Gate: APP_ENV is {app_env}, must be DEV. Aborting.")
        sys.exit(1)
        
    if args.confirm != "CONFIRM_NUKE":
        print("Safety Gate: Confirmation token invalid. Use --confirm CONFIRM_NUKE")
        sys.exit(1)

    # 1. Nuke
    nuke_db()
    
    # 2. Migrate
    print("Running Migrations...")
    # Assume running from inside container where alembic.ini is in /app (backend)
    # We are in backend/scripts, so parent is backend.
    cwd = str(Path(__file__).resolve().parents[1])
    run_command("alembic upgrade head", cwd=cwd)
    
    # 3. Seed
    print("Running Seed...")
    # Run as module to ensure imports work
    run_command(f"python -m scripts.seed_production --env DEV --dev-fixtures", cwd=cwd)
    
    # 4. Verify
    print("Running Verification...")
    run_command(f"python -m scripts.verify_seed_schema_completeness", cwd=cwd)
    
    # 5. Smoke Tests
    print("Running Smoke Tests...")
    run_command("pytest tests/seeding/ -q", cwd=cwd)
    run_command("pytest tests/smoke/ -q", cwd=cwd)

    print("WORKFLOW COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    main()
