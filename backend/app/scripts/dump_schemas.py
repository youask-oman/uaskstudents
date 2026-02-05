"""Dump ALL schema content from DB for inspection."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from app.database import get_session
from app.models import JsonSchemaEntry

def dump_schemas():
    """Dump all schema content to files for inspection."""
    output_dir = Path(__file__).parent / "schema_dumps"
    output_dir.mkdir(exist_ok=True)
    
    with next(get_session()) as session:
        schemas = list(session.query(JsonSchemaEntry).filter(JsonSchemaEntry.is_active == True).all())
        print(f"Found {len(schemas)} active schemas")
        
        for schema in schemas:
            content = schema.content if isinstance(schema.content, dict) else {}
            content_str = json.dumps(content, indent=2)
            
            # Save to file
            safe_name = schema.schema_id.replace("/", "_").replace("\\", "_")
            filename = f"{safe_name}_v{schema.version}.json"
            filepath = output_dir / filename
            with open(filepath, "w") as f:
                f.write(content_str)
            print(f"Saved: {filepath}")
            
            # Check for corruption patterns in string representation
            issues = []
            if '"type": "None"' in content_str:
                issues.append('"type": "None"')
            if '"type": null' in content_str:
                issues.append('"type": null')
            if '"None"' in content_str:
                issues.append('"None" found somewhere')
            if ': null' in content_str:
                # Only report if it's in a type context
                pass
                
            if issues:
                print(f"  ⚠️ Issues: {issues}")
            else:
                print(f"  ✅ No obvious issues")

if __name__ == "__main__":
    dump_schemas()
