"""
STEP 1: DB Audit Script
Finds all corrupted schema rows containing invalid JSON Schema types.

Search patterns:
- "type": "None"
- "type": null
- ["string", null] or ["string", "None"]
- anyOf/oneOf branches with nested null types
"""
import json
import re
import sys
from typing import List, Dict, Any, Tuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from app.database import get_session
from app.models import JsonSchemaEntry, PromptBinding


def find_corruption_paths(obj: Any, path: str = "$") -> List[Tuple[str, str]]:
    """
    Recursively search for invalid type declarations in a JSON structure.
    Returns list of (json_path, issue_description) tuples.
    """
    issues = []
    
    if isinstance(obj, dict):
        # Check for invalid "type" field
        if "type" in obj:
            type_val = obj["type"]
            
            # Case 1: "type": "None" (stringified Python None)
            if type_val == "None":
                issues.append((f"{path}.type", '"type": "None" (stringified Python None)'))
            
            # Case 2: "type": null (JSON null)
            elif type_val is None:
                issues.append((f"{path}.type", '"type": null (JSON null instead of "null" string)'))
            
            # Case 3: Array containing null or "None"
            elif isinstance(type_val, list):
                for i, item in enumerate(type_val):
                    if item is None:
                        issues.append((f"{path}.type[{i}]", f'Array contains null: {type_val}'))
                    elif item == "None":
                        issues.append((f"{path}.type[{i}]", f'Array contains "None": {type_val}'))
        
        # Recurse into nested structures
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            issues.extend(find_corruption_paths(value, child_path))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_path = f"{path}[{i}]"
            issues.extend(find_corruption_paths(item, child_path))
    
    return issues


def audit_schemas():
    """Query DB and find all corrupted schema rows."""
    results = []
    
    with next(get_session()) as session:
        # Get all schemas
        schemas = session.query(JsonSchemaEntry).filter(JsonSchemaEntry.is_active == True).all()
        print(f"\n{'='*80}")
        print(f"DB SCHEMA AUDIT REPORT")
        print(f"{'='*80}")
        print(f"Total active schemas: {len(schemas)}")
        
        corrupted_schemas = []
        
        for schema in schemas:
            content = schema.content if isinstance(schema.content, dict) else {}
            issues = find_corruption_paths(content)
            
            if issues:
                corrupted_schemas.append({
                    "id": schema.id,
                    "schema_id": schema.schema_id,
                    "version": schema.version,
                    "issues": issues
                })
        
        print(f"Corrupted schemas found: {len(corrupted_schemas)}")
        print()
        
        if not corrupted_schemas:
            print("✅ No corruption found!")
            return results
        
        # For each corrupted schema, find referencing PromptBindings
        print(f"\n{'='*80}")
        print("DETAILED CORRUPTION REPORT")
        print(f"{'='*80}\n")
        
        for cs in corrupted_schemas:
            print(f"Schema ID: {cs['schema_id']} (Row ID: {cs['id']}, Version: {cs['version']})")
            print(f"  Issues ({len(cs['issues'])}):")
            for path, desc in cs['issues']:
                print(f"    - {path}: {desc}")
            
            # Find PromptBindings referencing this schema
            bindings = session.query(PromptBinding).filter(
                PromptBinding.output_schema_id == cs["schema_id"],
                PromptBinding.is_active == True
            ).all()
            
            if bindings:
                print(f"  Referenced by PromptBindings:")
                for b in bindings:
                    print(f"    - Binding: {b.id[:8]}... | Tier: {b.tier.value} | Mode: {b.mode.value}")
            else:
                print(f"  Referenced by: (none)")
            
            print()
            
            results.append({
                "schema_id": cs["schema_id"],
                "row_id": cs["id"],
                "version": cs["version"],
                "issue_count": len(cs["issues"]),
                "issues": cs["issues"],
                "bindings": [{"id": b.id, "tier": b.tier.value, "mode": b.mode.value} for b in bindings]
            })
        
        # Summary table
        print(f"\n{'='*80}")
        print("SUMMARY TABLE")
        print(f"{'='*80}")
        print(f"{'Schema ID':<40} {'Issues':<8} {'Bindings':<10}")
        print("-" * 60)
        for r in results:
            print(f"{r['schema_id']:<40} {r['issue_count']:<8} {len(r['bindings']):<10}")
        
        return results


if __name__ == "__main__":
    audit_results = audit_schemas()
    
    # Save results to JSON for migration script
    output_path = Path(__file__).parent / "audit_results.json"
    with open(output_path, "w") as f:
        json.dump(audit_results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")
