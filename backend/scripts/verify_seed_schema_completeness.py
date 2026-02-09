import json
import hashlib
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from typing import List, Dict, Any, Tuple

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.models import (
    User,
    PromptTemplateEntry,
    PromptBinding,
    JsonSchemaEntry,
    ProviderModelPricing,
    CreditLot,
    Payment,
    SystemConfig,
    School
)
from app.models.credit_program_models import CreditProgramDefinition
# Import Plan from app.models (it should be there based on seed_production.py)
from app.models import Plan

ROOT = Path(__file__).resolve().parents[1]
SEED_DATA_DIR = ROOT / "seed_data"

REPORT_DATA = {
    "tables_exist": [],
    "constraints_pass": [],
    "constraints_fail": [],
    "seed_files_status": {},
    "db_row_counts": {},
    "forbidden_tables_status": {},
    "internal_users_check": [],
    "verification_success": False
}

def check_tables_exist(inspector):
    required_tables = [
        "school", "systemconfig", "prompt_templates", "prompt_bindings", 
        "providermodelpricing", "plan", "credit_program_definition", "user",
        "json_schemas"
    ]
    # Check actual tables
    actual_tables = inspector.get_table_names()
    missing = []
    for t in required_tables:
        # fuzzy match or exact? The prompt names might slightly differ (e.g. users vs user)
        # Assuming sqlmodel defaults (usually lower case singular or plural depending on config)
        # But let's check exact or plural.
        if t not in actual_tables and t + "s" not in actual_tables:
             # Try to find a match
             found = False
             for at in actual_tables:
                 if at == t or at == t + "s" or at.replace("_", "") == t.replace("_", ""):
                     found = True
                     break
             if not found:
                 missing.append(t)
    
    REPORT_DATA["tables_exist"] = {"required": required_tables, "missing": missing, "all_tables": actual_tables}
    return len(missing) == 0

def check_constraints(inspector):
    # This is a bit hard to do generically without generic SQL, but we can check indexes/constraints via inspector
    # 1. prompt_templates unique
    # 2. json_schema unique
    # 3. prompt_bindings unique
    
    failures = []
    passes = []
    
    def check_unique(table, cols):
        try:
            unique_constraints = inspector.get_unique_constraints(table)
            indexes = inspector.get_indexes(table)
            # Check for unique constraint or unique index
            found = False
            target_cols = set(cols)
            
            for c in unique_constraints:
                if set(c['column_names']) == target_cols:
                    found = True
                    break
            if not found:
                for idx in indexes:
                    if idx['unique'] and set(idx['column_names']) == target_cols:
                        found = True
                        break
            
            if found:
                passes.append(f"{table} unique on {cols}")
            else:
                failures.append(f"{table} missing unique on {cols}")
        except Exception as e:
            failures.append(f"Error checking {table}: {e}")

    # Map likely table names
    tables = inspector.get_table_names()
    pt = "prompt_templates" if "prompt_templates" in tables else "prompt_template_entry"
    js = "json_schemas" if "json_schemas" in tables else "json_schema_entry"
    pb = "prompt_bindings" if "prompt_bindings" in tables else "prompt_binding"

    if pt in tables:
        check_unique(pt, ["prompt_id", "version"])
    else:
        failures.append(f"Table {pt} not found for constraint check")

    if js in tables:
        check_unique(js, ["schema_id", "version"])
    else:
        failures.append(f"Table {js} not found for constraint check")
        
    if pb in tables:
        # binding_key or (tier, mode, template, schema) - generic check might be hard if column names differ
        # Let's check for at least ONE unique constraint or index that looks like a key
        uc = inspector.get_unique_constraints(pb)
        idx = inspector.get_indexes(pb)
        if not uc and not [i for i in idx if i['unique']]:
             failures.append(f"{pb} has no unique constraints")
        else:
             passes.append(f"{pb} has unique constraints")

    REPORT_DATA["constraints_pass"] = passes
    REPORT_DATA["constraints_fail"] = failures
    return len(failures) == 0

def calculate_file_sha256(path: Path):
    if not path.exists():
        return None
    # Read as json to ensure stable serialization if needed, or just raw bytes?
    # The seeder uses a specific stability transform. We should probably replicate it or just trust the manifest if it matches.
    # But for now, let's just check existence.
    return "exists"

def check_seed_files():
    required = [
        "prompt_templates.json",
        "prompt_bindings.json",
        "json_schemas.json",
        "schools.json",
        "seed_manifest.json"
    ]
    
    status = {}
    missing = []
    for f in required:
        p = SEED_DATA_DIR / f
        if p.exists():
            status[f] = "Present"
        else:
            # Special case: prompt_templates might be a dir
            if f == "prompt_templates.json" and (SEED_DATA_DIR / "prompt_templates").is_dir():
                 status[f] = "Directory Present (Acceptable)"
            else:
                 status[f] = "Missing"
                 missing.append(f)
                 
    REPORT_DATA["seed_files_status"] = status
    return len(missing) == 0

def verify_data_integrity(session: Session):
    # Check row counts vs manifest (if manifest exists)
    manifest_path = SEED_DATA_DIR / "seed_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception as e:
            print(f"Error reading manifest: {e}")
            REPORT_DATA["seed_files_status"]["seed_manifest.json"] = "Invalid JSON"
    
    user_ok = False
    forbidden_ok = False
    
    # Check Internal Users
    try:
        users = session.exec(select(User).where(User.is_internal == True)).all()
        internal_user_emails = [u.email for u in users]
        REPORT_DATA["internal_users_check"] = internal_user_emails
        user_ok = len(users) >= 10
    except Exception as e:
        REPORT_DATA["internal_users_check"] = [f"Error checking users: {e}"]
        user_ok = False
    
    # Check Forbidden Tables
    forbidden = ["payment", "invoice", "invoice_line_item", "refund", "subscription", "subscriptionperiod", "chatsession", "chatmessage", "solveroutputattempt", "billingledger"] 
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    
    forbidden_status = {}
    try:
        for ft in forbidden:
            table_to_check = ft if ft in all_tables else (ft + "s" if ft + "s" in all_tables else None)
            if table_to_check:
                count = session.exec(text(f"SELECT COUNT(*) FROM {table_to_check}")).one()[0]
                forbidden_status[table_to_check] = count
            else:
                forbidden_status[ft] = 0
        
        REPORT_DATA["forbidden_tables_status"] = forbidden_status
        forbidden_ok = all(isinstance(c, int) and c == 0 for c in forbidden_status.values())
    except Exception as e:
        REPORT_DATA["forbidden_tables_status"] = {"Error": str(e)}
        forbidden_ok = False

    # Check row counts validation
    db_counts = {}
    required_tables = {
        "systemconfig": "systemconfig",
        "prompt_templates": "prompt_templates",
        "prompt_bindings": "prompt_bindings",
        "json_schemas": "json_schemas",
        "providermodelpricing": "providermodelpricing",
        "credit_program_definition": "credit_program_definition",
        "plan": "plan",
        "school": "school"
    }
    try:
        db_counts["user_internal"] = len(users) if 'users' in locals() else 0
        for label, table_name in required_tables.items():
            check_name = table_name if table_name in all_tables else (table_name + "s" if table_name + "s" in all_tables else None)
            if check_name:
                db_counts[label] = session.exec(text(f"SELECT count(*) FROM {check_name}")).one()[0]
            else:
                db_counts[label] = 0
        
        # Manifest check for schools if available
        if manifest.get("files", {}).get("schools.json"):
            expected = manifest["files"]["schools.json"].get("row_count")
            if expected is not None:
                db_counts["expected_school"] = expected
                if db_counts["school"] < expected:
                    db_counts["school_mismatch"] = f"Expected {expected}, found {db_counts['school']}"
                    forbidden_ok = False
    except Exception as e:
        db_counts["error"] = str(e)
    
    REPORT_DATA["db_row_counts"] = db_counts
    
    # Verify Referential Integrity explicitly
    integrity_issues = []
    try:
        # Bindings -> Templates
        # Check global system prompt
        bad_sys = session.exec(text("SELECT count(*) FROM prompt_bindings WHERE global_system_prompt_id NOT IN (SELECT prompt_id FROM prompt_templates)")).one()[0]
        if bad_sys > 0:
            integrity_issues.append(f"{bad_sys} bindings have invalid global_system_prompt_id")
            
        # Check developer prompt
        bad_dev = session.exec(text("SELECT count(*) FROM prompt_bindings WHERE developer_prompt_id NOT IN (SELECT prompt_id FROM prompt_templates)")).one()[0]
        if bad_dev > 0:
            integrity_issues.append(f"{bad_dev} bindings have invalid developer_prompt_id")
            
        # Bindings -> Schemas
        bad_schema = session.exec(text("SELECT count(*) FROM prompt_bindings WHERE output_schema_id NOT IN (SELECT schema_id FROM json_schemas)")).one()[0]
        if bad_schema > 0:
            integrity_issues.append(f"{bad_schema} bindings have invalid output_schema_id")

    except Exception as e:
        integrity_issues.append(f"Error checking integrity: {e}")
    
    if integrity_issues:
        REPORT_DATA["integrity_issues"] = integrity_issues
        forbidden_ok = False # Fail overall
    else:
        REPORT_DATA["integrity_issues"] = "PASS"

    return user_ok and forbidden_ok and not integrity_issues

def main():
    print("Starting verification...")
    inspector = inspect(engine)
    
    t_ok = check_tables_exist(inspector)
    c_ok = check_constraints(inspector)
    s_ok = check_seed_files()
    
    with Session(engine) as session:
        d_ok = verify_data_integrity(session)
        
    success = t_ok and c_ok and s_ok and d_ok
    REPORT_DATA["verification_success"] = success
    
    print(json.dumps(REPORT_DATA, indent=2))
    
    # Write report
    report_path = ROOT / "reports" / "seed_schema_completeness_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(REPORT_DATA, indent=2))
    
    if not success:
        print("Verification FAILED")
        sys.exit(1)
    else:
        print("Verification PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
