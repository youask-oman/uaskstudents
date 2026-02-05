"""
Audit Bindings → Schemas

Deep-scans all prompt_bindings and their referenced schemas for corruption.
Validates schema wrapper format and scans for type: "None" or type: null.
"""
import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Setup path
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env from project root (not backend)
from dotenv import load_dotenv
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

# Production DATABASE_URL fallback
os.environ.setdefault("DATABASE_URL", "postgresql://uaskstudents_user:MJxQ25u6zNRFyp396NUyXxPPuvD9YcVU@dpg-ctd020m8ii6s73a1l8u0-a.oregon-postgres.render.com/uaskstudents")

from sqlmodel import Session, create_engine, select
from app.models import PromptBinding, JsonSchemaEntry


def compute_schema_hash(schema_dict: Dict[str, Any]) -> str:
    """Compute SHA256 hash of schema JSON for comparison."""
    return hashlib.sha256(
        json.dumps(schema_dict, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()[:16]


def find_bad_type_paths(node: Any, path: str = "$") -> List[Tuple[str, str]]:
    """
    Recursively find all paths where type is null, None, or "None".
    Returns list of (path, issue_description) tuples.
    """
    issues = []
    
    if not isinstance(node, dict):
        if isinstance(node, list):
            for i, item in enumerate(node):
                issues.extend(find_bad_type_paths(item, f"{path}[{i}]"))
        return issues
    
    # Check "type" field
    if "type" in node:
        type_val = node["type"]
        
        if type_val is None:
            issues.append((f"{path}.type", "type is Python None (will serialize as null)"))
        elif type_val == "None":
            issues.append((f"{path}.type", 'type is string "None" (invalid)'))
        elif type_val == "null":
            # This has an edge case - "null" is valid in type arrays but not as standalone
            # Check if it's standalone at root level with properties
            if "properties" in node or path == "$":
                issues.append((f"{path}.type", 'type is "null" but node has properties (should be "object")'))
        elif isinstance(type_val, list):
            for i, item in enumerate(type_val):
                if item is None:
                    issues.append((f"{path}.type[{i}]", "array contains Python None"))
                elif item == "None":
                    issues.append((f"{path}.type[{i}]", 'array contains string "None"'))
    
    # Recurse into nested structures
    for key, value in node.items():
        if isinstance(value, dict):
            issues.extend(find_bad_type_paths(value, f"{path}.{key}"))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                issues.extend(find_bad_type_paths(item, f"{path}.{key}[{i}]"))
    
    return issues


def validate_wrapper_format(schema: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate schema follows our DB wrapper format.
    Expected: {"type": "json_schema", "name": "...", "strict": bool, "schema": {...}}
    """
    if not isinstance(schema, dict):
        return False, "Not a dict"
    
    # Check wrapper keys
    if schema.get("type") != "json_schema":
        return False, f"wrapper.type is not 'json_schema', got: {schema.get('type')!r}"
    
    if "name" not in schema:
        return False, "wrapper missing 'name' key"
    
    if "schema" not in schema:
        return False, "wrapper missing 'schema' key"
    
    if not isinstance(schema.get("schema"), dict):
        return False, "wrapper.schema is not a dict"
    
    inner = schema["schema"]
    if inner.get("type") not in ("object", "array", "string", "number", "integer", "boolean"):
        # Check for null type at root
        if inner.get("type") is None:
            return False, "inner.type is None (missing type at root)"
        if inner.get("type") == "None":
            return False, 'inner.type is string "None" (invalid)'
        return False, f"inner.type is unexpected: {inner.get('type')!r}"
    
    return True, "OK"


def audit_bindings_schemas():
    """Main audit function."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return
    
    # Determine if SSL is needed (remote DB) or not (localhost)
    is_localhost = "localhost" in database_url or "127.0.0.1" in database_url or "postgres" in database_url
    connect_args = {} if is_localhost else {"sslmode": "require", "connect_timeout": 10}
    
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0
    )
    
    print("=" * 80)
    print("BINDINGS -> SCHEMAS AUDIT REPORT")
    print("=" * 80)
    print()
    
    with Session(engine) as session:
        # Get all active bindings
        bindings = list(session.exec(
            select(PromptBinding).where(PromptBinding.is_active == True)
        ).all())
        
        print(f"Found {len(bindings)} active bindings")
        print()
        
        # Table header
        print(f"{'Binding ID':<40} {'Tier':<12} {'Mode':<15} {'Schema ID':<50} {'Valid':<8} {'Issues'}")
        print("-" * 160)
        
        issues_found = []
        
        for binding in bindings:
            schema_id = binding.output_schema_id
            
            # Resolve schema
            schema_entry = session.exec(
                select(JsonSchemaEntry).where(
                    JsonSchemaEntry.schema_id == schema_id,
                    JsonSchemaEntry.is_active == True
                )
            ).first()
            
            if not schema_entry:
                print(f"{binding.id:<40} {binding.tier.value:<12} {binding.mode.value:<15} {schema_id:<50} {'NO':<8} Schema not found!")
                issues_found.append({
                    "binding_id": binding.id,
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "schema_id": schema_id,
                    "issue": "Schema entry not found in DB"
                })
                continue
            
            content = schema_entry.content
            
            # Validate wrapper format
            wrapper_valid, wrapper_msg = validate_wrapper_format(content)
            
            # Deep scan for bad types
            inner_schema = content.get("schema", content) if isinstance(content, dict) else {}
            bad_paths = find_bad_type_paths(inner_schema)
            
            # Determine overall status
            if not wrapper_valid:
                status = "NO"
                issue_summary = f"Wrapper: {wrapper_msg}"
            elif bad_paths:
                status = "NO"
                issue_summary = f"Bad types: {', '.join([p[0] for p in bad_paths[:3]])}"
                if len(bad_paths) > 3:
                    issue_summary += f" (+{len(bad_paths)-3} more)"
            else:
                status = "OK"
                issue_summary = ""
            
            schema_name = content.get("name", "?") if isinstance(content, dict) else "?"
            display_schema_id = f"{schema_id} ({schema_name})"
            
            print(f"{binding.id:<40} {binding.tier.value:<12} {binding.mode.value:<15} {display_schema_id:<50} {status:<8} {issue_summary}")
            
            if status != "OK":
                issues_found.append({
                    "binding_id": binding.id,
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "schema_id": schema_id,
                    "schema_name": schema_name,
                    "wrapper_valid": wrapper_valid,
                    "wrapper_msg": wrapper_msg,
                    "bad_paths": bad_paths
                })
        
        print()
        print("=" * 80)
        print(f"SUMMARY: {len(bindings)} bindings checked, {len(issues_found)} with issues")
        print("=" * 80)
        
        if issues_found:
            print("\nDETAILED ISSUES:")
            for issue in issues_found:
                print(f"\n  Binding: {issue['binding_id']}")
                print(f"    Tier/Mode: {issue['tier']} / {issue['mode']}")
                print(f"    Schema: {issue['schema_id']}")
                if 'bad_paths' in issue and issue['bad_paths']:
                    print(f"    Bad Paths:")
                    for path, desc in issue['bad_paths']:
                        print(f"      - {path}: {desc}")
                if 'wrapper_msg' in issue and issue['wrapper_msg'] != "OK":
                    print(f"    Wrapper Issue: {issue['wrapper_msg']}")
        else:
            print("\n✅ All bindings reference valid schemas!")
        
        # Also dump raw SQL query for inclusion in report
        print("\n" + "=" * 80)
        print("RAW BINDING DATA (for trace report)")
        print("=" * 80)
        print(f"{'Binding ID':<40} {'Tier':<12} {'Mode':<15} {'Schema ID':<50} {'Max Tokens'}")
        print("-" * 130)
        for b in bindings:
            print(f"{b.id:<40} {b.tier.value:<12} {b.mode.value:<15} {b.output_schema_id:<50} {b.max_output_tokens or 'N/A'}")


if __name__ == "__main__":
    audit_bindings_schemas()
