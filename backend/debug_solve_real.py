
import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Ensure we can import app modules
sys.path.append(os.path.join(os.getcwd(), "backend"))

load_dotenv()

from app.services.solver_v3 import get_solver_v3

async def main():
    print("Initializing SolverV3...")
    solver = get_solver_v3()
    
    problem = r"inverse laplace \frac{1}{s(s+2)}"
    print(f"Attempting to solve: {problem}")
    
    try:
        # We use a mocked session or None. expecting SolverV3 to handle None for basic test.
        # However, the error is Schema related, which happens deep in _call_llm_with_schema.
        # We need to ensure we hit the OpenAi path.
        
        # Note: SolverV3 logic requires db_session for ProfileResolver if user_id is passed.
        # If no user_id, it uses get_prompt_profile(user_tier) which mocks the profile.
        # The user's error happens with the REAL app, which likely has a user_id and hits the DB.
        # But if the schema is static, the mocked profile might NOT load it from the file?
        # Check `get_prompt_profile` in `backend/app/llm_profiles/profiles.py`.
        
        # Let's try running without DB first (free tier default).
        # If that passes, it means the error is specific to the DB-loaded profile (the static file).
        # We want to force usage of the static schema file.
        
        # BUT, previously I saw `solver_v3.py` logic:
        # if db_session: ... ProfileResolver ...
        # else: ... get_prompt_profile ...
        
        # So to test the static schema file, I MUST force the profile that uses it.
        # Or I can manually inject the problematic schema to `solve` call via `json_schema_config`?
        # `SolverV3.solve` takes `requested_mode="minimal"`.
        
        response = await solver.solve(
            problem_text=problem,
            trace=True,
            requested_mode="minimal", # likely the mode causing issues
            user_tier="free"
        )
        
        print("\nSolve Success!")
        # print(json.dumps(response, indent=2))

    except Exception as e:
        print(f"\nSolve Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
