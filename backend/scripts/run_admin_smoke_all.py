import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

# Path setup
BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
REPORTS_DIR = BACKEND_DIR / "reports"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_command(cmd, cwd=None, env=None):
    log(f"CMD: {cmd}")
    try:
        res = subprocess.run(
            cmd, shell=True, cwd=str(cwd or BACKEND_DIR), 
            capture_output=True, text=True, env={**os.environ, **(env or {})}
        )
        if res.returncode != 0:
            log(f"FAILED (code {res.returncode})")
            print(res.stdout)
            print(res.stderr)
            return False, res.stdout, res.stderr
        return True, res.stdout, res.stderr
    except Exception as e:
        log(f"EXCEPTION: {e}")
        return False, "", str(e)

def main():
    log("=== ADMIN DASHBOARD COMPREHENSIVE SMOKE TEST ===")
    
    # 1. Clean Recreate
    log("Step 1: Recreating DEV Database & Seeding...")
    # Using the existing script but with --confirm
    ok, stdout, stderr = run_command("python scripts/dev_recreate_db_and_seed.py --confirm RESET_DEV_DB")
    if not ok:
        log("Database recreate FAILED. Aborting.")
        sys.exit(1)
        
    # 2. Route Discovery
    log("Step 2: Discovering Routes...")
    ok, stdout, stderr = run_command("python scripts/discover_admin_routes.py")
    if not ok:
        log("Route discovery FAILED. Aborting.")
        sys.exit(1)
        
    # 3. Running Smoke Tests
    log("Step 3: Running Automated Smoke Tests...")
    # Note: we use pytest inside the container's context or host. 
    # Since we are likely running this inside the container if called via 'docker compose exec',
    # we just run pytest directly.
    ok, stdout, stderr = run_command("pytest tests/smoke/test_admin_rbac.py tests/smoke/test_admin_api_all.py tests/smoke/test_admin_pages_all.py -v")
    
    # 4. Generate Final Report
    log("Step 4: Generating Final Report...")
    generate_final_report(stdout if ok else stdout + "\n" + stderr)
    
    if ok:
        log("=== ALL TESTS PASSED SUCCESSFULLY ===")
        sys.exit(0)
    else:
        log("=== SOME TESTS FAILED ===")
        sys.exit(1)

def generate_final_report(pytest_output):
    inventory_path = REPORTS_DIR / "admin_route_inventory.json"
    results_path = REPORTS_DIR / "admin_api_test_results.json"
    
    inventory = {"backend_endpoints": [], "ui_pages": []}
    if inventory_path.exists():
        with open(inventory_path, "r") as f:
            inventory = json.load(f)
            
    results = []
    if results_path.exists():
        with open(results_path, "r") as f:
            results = json.load(f)
            
    # Calculate stats
    passed_apis = [r for r in results if r.get("status") == "PASS"]
    failed_apis = [r for r in results if r.get("status") != "PASS"]
    
    avg_ms = sum(r.get("ms", 0) for r in passed_apis) / len(passed_apis) if passed_apis else 0
    p95_ms = sorted([r.get("ms", 0) for r in passed_apis])[int(0.95 * len(passed_apis))] if passed_apis else 0

    content = f"""# Admin Dashboard Test Report
    
**Date:** {datetime.now(timezone.utc).isoformat()}  
**Status:** {"SUCCESS" if failed_apis == [] else "FAILED"}

## 1. Inventory Summary
- **Admin UI Pages:** {len(inventory.get("ui_pages", []))}
- **Admin Backend Endpoints:** {len(inventory.get("backend_endpoints", []))}

## 2. API Test Results
- **Passed:** {len(passed_apis)}
- **Failed:** {len(failed_apis)}
- **Avg Response Time:** {avg_ms:.2f}ms
- **P95 Response Time:** {p95_ms:.2f}ms

### Top Failures
"""
    if not failed_apis:
        content += "None! All tested endpoints returned 200/404/valid JSON.\n"
    else:
        for f in failed_apis[:10]:
            content += f"- `{f.get('path')}`: {f.get('status')} (Code: {f.get('code')})\n"

    content += "\n## 3. Discovered UI Pages (Tabs)\n"
    for page in inventory.get("ui_pages", []):
        content += f"- {page}\n"

    content += "\n## 4. Pytest Output Summary\n```\n"
    # Take last 100 lines of pytest output to keep report readable
    lines = pytest_output.splitlines()
    content += "\n".join(lines[-100:])
    content += "\n```\n"

    report_md = REPORTS_DIR / "admin_tabs_and_links_test_report.md"
    report_md.write_text(content, encoding="utf-8")
    log(f"Final report written to {report_md}")

if __name__ == "__main__":
    main()
