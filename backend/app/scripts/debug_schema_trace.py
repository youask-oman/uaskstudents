"""Debug script to trace schema payload sent to OpenAI."""
import os
import sys
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql://uaskstudents_user:MJxQ25u6zNRFyp396NUyXxPPuvD9YcVU@dpg-ctd020m8ii6s73a1l8u0-a.oregon-postgres.render.com/uaskstudents")

from dotenv import load_dotenv
load_dotenv()

from sqlmodel import Session, create_engine
from app.prompts.db_loader import load_prompt_bundle

def debug_schema():
    engine = create_engine(os.getenv("DATABASE_URL"))
    
    with Session(engine) as session:
        # Test FREE tier
        print("=== Loading FREE tier bundle ===")
        bundle = load_prompt_bundle(
            tier="free",
            mode="solve",
            session=session,
        )
        
        schema = bundle.get("schema")
        print(f"Schema keys: {schema.keys() if isinstance(schema, dict) else type(schema)}")
        
        # Check top-level type
        if isinstance(schema, dict):
            print(f"Top-level type: {schema.get('type')!r}")
            
            # Check if wrapper
            if "schema" in schema:
                inner = schema["schema"]
                print(f"Inner schema type: {inner.get('type')!r}")
                
                # Deep search for "None"
                schema_str = json.dumps(schema, indent=2)
                if '"None"' in schema_str or '"type": null' in schema_str:
                    print("\n⚠️ CORRUPTION FOUND IN DB SCHEMA!")
                    # Find lines
                    for i, line in enumerate(schema_str.split('\n'), 1):
                        if '"None"' in line or '"type": null' in line:
                            print(f"  Line {i}: {line.strip()}")
                else:
                    print("\n✅ DB schema looks clean")
        
        # Now test what prepare_schema does
        print("\n=== Testing prepare_schema ===")
        from app.utils.schema_deref import deref_json_schema
        from app.utils.schema_cleaner import enforce_strict
        
        candidate = schema
        if "schema" in candidate and isinstance(candidate["schema"], dict):
            candidate = candidate["schema"]
            print(f"Unwrapped to inner schema, type: {candidate.get('type')!r}")
        
        deref = deref_json_schema(candidate)
        print(f"After deref, type: {deref.get('type')!r}")
        
        strict = enforce_strict(deref)
        print(f"After enforce_strict, type: {strict.get('type')!r}")
        
        # Deep search final schema
        final_str = json.dumps(strict, indent=2)
        if '"None"' in final_str:
            print("\n⚠️ CORRUPTION AFTER enforce_strict!")
            for i, line in enumerate(final_str.split('\n'), 1):
                if '"None"' in line:
                    print(f"  Line {i}: {line.strip()}")
        else:
            print("\n✅ Final schema clean after enforce_strict")

if __name__ == "__main__":
    debug_schema()
