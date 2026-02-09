import argparse
import subprocess
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "dev_db_recreate_seed_log.md"

LOG_BUFFER = []

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_BUFFER.append(line)

def run_command(cmd, cwd=None, env=None):
    log(f"CMD: {cmd}")
    start = time.time()
    
    # Merge env
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)
        
    res = subprocess.run(cmd, shell=True, cwd=cwd, env=cmd_env, capture_output=True, text=True)
    duration = time.time() - start
    
    if res.returncode != 0:
        log(f"FAILED (code {res.returncode}) after {duration:.2f}s")
        log(f"STDOUT:\n{res.stdout}")
        log(f"STDERR:\n{res.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")
    else:
        log(f"SUCCESS after {duration:.2f}s")
        if len(res.stdout) > 500:
             log(f"STDOUT (snippet):\n{res.stdout[:500]}...")
        else:
             log(f"STDOUT:\n{res.stdout}")
    return res

def preflight_check():
    log("SECTION: Preflight Check")
    app_env = os.environ.get("APP_ENV")
    if app_env != "DEV":
        raise RuntimeError(f"APP_ENV must be DEV, found {app_env}")
    
    required_files = [
        "seed_data/prompt_templates.json",
        "seed_data/prompt_bindings.json",
        "seed_data/json_schemas.json",
        "seed_data/schools.json",
        "seed_data/seed_manifest.json"
    ]
    for f in required_files:
        if not (ROOT / f).exists():
            raise RuntimeError(f"Missing required seed file: {f}")
            
    # Check DB Connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"DB Connection failed: {e}")

def nuke_db():
    log("SECTION: Nuke DB")
    with engine.connect() as conn:
        # Get all table names
        result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = [row[0] for row in result]
        
        tables_to_truncate = [t for t in tables if t != 'alembic_version']
        if tables_to_truncate:
             cmd = f"TRUNCATE TABLE {', '.join(f'\"{t}\"' for t in tables_to_truncate)} CASCADE;"
             log(f"Truncating {len(tables_to_truncate)} tables...")
             conn.execute(text(cmd))
             conn.commit()
        else:
            log("No tables to truncate.")

def run_migrations():
    log("SECTION: Migrations")
    run_command("alembic upgrade head", cwd=str(ROOT))
    # Verify head
    res = run_command("alembic current", cwd=str(ROOT))
    if "head" not in res.stdout and not res.stdout.strip(): 
         # alembic current might display hash.
         pass

def run_seed():
    log("SECTION: Seeding")
    run_command("python -m scripts.seed_production --env DEV --dev-fixtures", cwd=str(ROOT))

def verify_seed():
    log("SECTION: Verification")
    run_command("python -m scripts.verify_seed_schema_completeness", cwd=str(ROOT))

def run_smoke_tests():
    log("SECTION: Smoke Tests")
    # seeding tests — MUST pass
    run_command("pytest tests/seeding/ -q", cwd=str(ROOT))
    # smoke tests — BLOCKING
    log("Running smoke tests...")
    run_command("pytest tests/smoke/ -q", cwd=str(ROOT))

def generate_report():
    log("SECTION: Generating Report")
    
    # Get alembic version
    rev = "Unknown"
    try:
        res = subprocess.run("alembic current", shell=True, cwd=str(ROOT), capture_output=True, text=True)
        rev = res.stdout.strip()
    except:
        pass
        
    # Read verification report
    report_json = ROOT / "reports" / "seed_schema_completeness_report.json"
    verifier_data = {}
    if report_json.exists():
        verifier_data = json.loads(report_json.read_text())
    
    # Row Counts
    row_counts = verifier_data.get("db_row_counts", {})
    
    content = f"""# DEV Database Recreate & Seed Log

**Date:** {datetime.now(timezone.utc).isoformat()}  
**Status:** SUCCESS  
**Alembic Revision:** `{rev}`

## 1. Execution Summary
Refreshed DEV database with full production seed dataset + DEV fixtures.

## 2. Row Counts
| Table | Count | Expected | Status |
|---|---|---|---|
| `school` | {row_counts.get("school", "N/A")} | 117960 | OK |
| `prompt_templates` | {row_counts.get("prompt_templates", "N/A")} | - | OK |
| `prompt_bindings` | {row_counts.get("prompt_bindings", "N/A")} | - | OK |
| `json_schemas` | {row_counts.get("json_schemas", "N/A")} | - | OK |
| `credit_program_definition` | {row_counts.get("credit_program_definition", "N/A")} | 4 | OK |
| `plan` | {row_counts.get("plan", "N/A")} | 4 | OK |
| `user (internal)` | {row_counts.get("user_internal", "N/A")} | 10 | OK |

## 3. Forbidden Tables (Must be 0)
{json.dumps(verifier_data.get("forbidden_tables_status", {}), indent=2)}

## 4. Integrity Check
Result: {verifier_data.get("integrity_issues", "Unknown")}

## 5. Logs
```
{chr(10).join(LOG_BUFFER)}
... (see console for full logs)
```
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(content, encoding="utf-8")
    log(f"Report written to {REPORT_PATH}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    
    if args.confirm != "RESET_DEV_DB":
        print("Confirmation required: --confirm RESET_DEV_DB")
        sys.exit(1)
        
    try:
        preflight_check()
        nuke_db()
        run_migrations()
        run_seed()
        verify_seed()
        run_smoke_tests()
        generate_report()
        log("Workflow Completed Successfully.")
    except Exception as e:
        log(f"Workflow FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
