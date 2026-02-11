
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Load critical env vars manually
os.environ["OPENAI_API_KEY"] = "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"
os.environ["OPENAI_MODEL_DEFAULT"] = "gpt-5-mini" 

if "DATABASE_URL" not in os.environ:
    pass

from app.database import engine, Session
from app.services.solver_v3 import get_solver_v3
from app.models import User

async def main():
    problem_text = "Find and classify the critical points of f(x) = x^3 - 3x + ln(x) on its domain."
    context = "Subject: Calculus, Difficulty: University"
    
    print(f"--- Reproducing with FIXES for problem: {problem_text} ---")
    print(f"Using model: {os.environ['OPENAI_MODEL_DEFAULT']}")

    solver = get_solver_v3()
    
    try:
        with Session(engine) as db:
            print("Running solver.solve()...")
            try:
                # We specifically want to trigger RESEARCH tier if possible to test that path,
                # but "standard" user might get upgraded or we force it?
                # User set "user_tier" arg.
                result = await solver.solve(
                    problem_text=problem_text,
                    context=context,
                    trace=True,
                    user_tier="research",  # FORCE RESEARCH TIER to test binding/token logic
                    user_id=1,        
                    db_session=db,
                    requested_mode="detailed", # ensure detailed schema is used
                    max_output_tokens=None # Let it derive from binding/policy
                )
                print("Solver SUCCESS!")
                # Check for telemetry -> binding_meta
                if "telemetry" in result and "binding_meta" in result["telemetry"]:
                    print("Found Binding Meta:", result["telemetry"]["binding_meta"])
                else: 
                     print("WARNING: Binding Meta MISSING in telemetry")
                
            except Exception as e:
                print("\n!!! CAUGHT EXCEPTION !!!")
                print(f"Type: {type(e)}")
                print(f"Message: {e}")
                import traceback
                traceback.print_exc()
            
    except Exception as exc:
        print(f"DB Error or Setup Error: {exc}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
