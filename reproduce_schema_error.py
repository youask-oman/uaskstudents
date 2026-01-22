
import sys
import os
import json


# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3
from app.utils.schema_deref import deref_json_schema
from app.utils.schema_cleaner import enforce_strict

def main():
    try:
        print("Test 1: Dynamic Schema Generation")
        raw_schema = get_json_schema_for_openai_v3()
        # Note: get_json_schema_for_openai_v3 already calls enforce_strict now
        
        # Check for type: None or type: "None"
        schema_str = json.dumps(raw_schema, indent=2)
        
        with open("backend/final_schema_dump_dynamic.json", "w") as f:
            f.write(schema_str)
            
        print("Dynamic schema dumped to backend/final_schema_dump_dynamic.json")
        
        # recursive search for type: "None"
        def search_bad_type(node, path=""):
            if isinstance(node, dict):
                if node.get("type") == "None" or node.get("type") is None:
                     if "properties" in node or "additionalProperties" in node:
                        print(f"FOUND BAD TYPE at {path}: {node.get('type')}")
                
                # Check for type: ["string", "null"] which is invalid for strict
                if isinstance(node.get("type"), list):
                     print(f"FOUND LIST TYPE at {path}: {node.get('type')}")

                for k, v in node.items():
                    search_bad_type(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    search_bad_type(item, f"{path}[{i}]")

        print("Checking Dynamic Schema...")
        search_bad_type(raw_schema)

        # Test 2: Simulate Static Schema Loading (like SolverV3 does)
        print("\nTest 2: Static Schema Loading Simulation")
        # Load canonical schema file
        with open("backend/app/llm_profiles/shared/canonical_schema.json", "r") as f:
            static_schema = json.load(f)
            
        # Simulate SolverV3.load_schema logic
        deref = deref_json_schema(static_schema)
        final_static = enforce_strict(deref)
        
        with open("backend/final_schema_dump_static.json", "w") as f:
            f.write(json.dumps(final_static, indent=2))
            
        print("Static schema dumped to backend/final_schema_dump_static.json")
        print("Checking Static Schema...")
        search_bad_type(final_static)

        # Test 3: Streaming Path Simulation
        print("\nTest 3: Streaming Path Simulation")
        # Streaming path logic:
        # schema_wrapper = {
        #     "name": "solve_response_v3",
        #     "strict": True,
        #     "schema": enforce_strict(deref_json_schema(static_schema)) # Using static schema as if from profile
        # }
        streaming_schema = enforce_strict(deref_json_schema(static_schema))
        
        with open("backend/final_schema_dump_streaming.json", "w") as f:
            f.write(json.dumps(streaming_schema, indent=2))
            
        print("Streaming schema dumped to backend/final_schema_dump_streaming.json")
        print("Checking Streaming Schema...")
        search_bad_type(streaming_schema)
        
        print("\nVerification Complete.")


    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
