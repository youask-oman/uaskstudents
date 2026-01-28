import sys
import os
import asyncio
import json
from pathlib import Path

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from dotenv import load_dotenv
env_path = backend_dir.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from app.services.solver_v3 import SolverV3
from app.llm_profiles.profiles import PromptProfile
from app.utils.schema_deref import deref_json_schema

async def main():
    print("Initializing SolverV3...")
    solver = SolverV3()
    
    # Load canonical schema to test the production format
    schema_path = os.path.join(backend_dir, "app", "llm_profiles", "shared", "canonical_schema.json")
    print(f"Loading schema from: {schema_path}")
    with open(schema_path, "r", encoding="utf-8-sig") as f:
        schema_raw = json.load(f)
        
    # OpenAI expects a self-contained schema without $ref/$defs.
    # We use deref_json_schema to inline the definitions.
    schema_wrapped = deref_json_schema(schema_raw)
    
    # Try stripping some complex metadata blocks to see if it fixes "accessibility" error
    if "meta" in schema_wrapped["schema"]["properties"]:
        schema_wrapped["schema"]["properties"]["meta"]["properties"].pop("ui_intent", None)
        schema_wrapped["schema"]["properties"]["meta"]["required"] = [
            r for r in schema_wrapped["schema"]["properties"]["meta"]["required"] if r != "ui_intent"
        ]
    
    # Unwrapping the schema for the PromptProfile but manual_test_solve.py 
    # will pass it to _call_llm_with_schema which expects the inner schema
    # if it's already wrapped or vice versa?
    # SolverV3._call_llm_with_schema:
    #   schema_payload = json_schema_config
    #   "schema": schema_payload.get("schema", schema_payload)
    # If we pass schema_wrapped, schema_payload.get("schema") is the inner schema.
    
    profile = PromptProfile(
        tier="pro",
        json_schema_content=schema_wrapped,
        system_prompt_content="You are a helpful math tutor. Break down the problem into logical steps. Use the provided JSON schema.",
        max_output_tokens=4000,
        max_steps=10
    )
    
    problem = r"Solve for x: (x+1)/(x-2) = 3" # Simpler problem text
    print(f"Solving problem: {problem}")
    
    try:
        data, status, tokens = await solver._call_llm_with_schema(
            problem_text=problem,
            context="",
            system_prompt=profile.system_prompt_content,
            json_schema_config=profile.json_schema_content,
            max_output_tokens=profile.max_output_tokens,
            trace=True,
            requested_mode="detailed"
        )
        
        result = {
            "data": data,
            "status": status,
            "tokens": tokens
        }
        
        output_file = "solve_output_v2_lite.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2))
            
        print(f"Results saved to {output_file}")
        if data:
            print(f"Final Answer: {data.get('answer', {}).get('final_text', 'N/A')}")
        else:
            print(f"Error: {status}")

    except Exception:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
