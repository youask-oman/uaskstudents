
import sys
import os
import asyncio
import json

# Correctly add the 'backend' folder to sys.path so 'app' module can be found
# If running from e:\uaskstudents, backend is subdir.
# If running from e:\uaskstudents\backend, it is current dir.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
# Also add parent if we are in backend to treat backend as source root?
# Actually 'app' is inside 'backend'. So backend/ needs to be in path.
# This was already done, but let's be explicit.
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), "backend"))
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

from app.services.solver_v3 import get_solver_v3
from app.services.llm.manager import get_llm_manager
from sqlmodel import Session
from app.database import engine

# Test Configuration
USE_MOCK_LLM = False # User requested REAL LLM
# Complex problem that was causing truncation/issues
PROBLEM_TEXT = "Solve for all real x: x^3 - 3x + 1 = 2\\cos x" # Use LaTeX for cos

if USE_MOCK_LLM:
    print("WARNING: Using MOCK LLM (Validation not fully guaranteed)")

# --- Mock & Setup ---
import app.services.solver_v3
from app.database import engine # Use REAL database engine
from sqlmodel import Session

# We need to override the dependency, or just use the session directly
def get_db_session():
    return Session(engine)

async def verify_fix():
    print("Initializing SolverV3 with Fix Verification (COMPLEX PROBLEM)...")
    
    # 1. Setup Solver
    solver = get_solver_v3()
    
    # ... (Setup Mock if needed - skipped since False) ...

    # 2. Run Solve for key tiers
    tiers_to_test = ["free", "standard", "research"]
    results = {}

    with get_db_session() as session:
        print(f"[VERIFY] using database session: {session.bind.url}")
        
        for tier in tiers_to_test:
            # User Rule: Free tier must have graph_mode="off"
            graph_mode_arg = "off" if tier == "free" else "on"
            
            print(f"\n[VERIFYING TIER: {tier.upper()}] with mode=minimal, graph_mode={graph_mode_arg}")
            try:
                # Direct call to solve
                response = await solver.solve(
                    problem_text=PROBLEM_TEXT,
                    user_tier=tier,
                    requested_mode="minimal", # The "minimal" mode that was problematic
                    requests_graph_mode=graph_mode_arg, # Separate pipeline trigger
                    db_session=session, # Pass REAL session for prompt loading
                    trace=True
                )
                
                # Check for Plot Spec
                has_visuals = response.get("visuals", {}).get("should_visualize", False)
                plot_generated = response.get("_telemetry", {}).get("plot_generated", False)
                plot_data = response.get("visuals", {}).get("plots") or response.get("plot_spec")
                
                # Check for truncated solve
                solve_error = response.get("error")
                solve_status_checks = response.get("_telemetry", {}).get("status_checks", [])
                solve_status = solve_status_checks[0].get("finish_reason") if solve_status_checks else None
                
                results[tier] = {
                    "ok": not solve_error,
                    "solve_truncated": solve_status == "length",
                    "plot_present": bool(has_visuals and plot_data),
                    "plot_data_type": str(type(plot_data)),
                    "output_tokens_solve": response.get("_telemetry", {}).get("output_tokens"),
                    # "output_tokens_plot": response.get("_telemetry", {}).get("plot_pipeline", {}).get("usage") # Not tracked yet fully in telemetry dict structure I added?
                    # I added `telemetry["plot_pipeline"]`.
                }
                
                # Save raw responses
                with open(f"backend/fix_verify_{tier}.json", "w", encoding="utf-8") as f:
                    json.dump(response, f, indent=2)

                print(f"[{tier.upper()}] Success: {results[tier]['ok']}")
                print(f"    Plot Present: {results[tier]['plot_present']}")
                print(f"    Solve Truncated: {results[tier]['solve_truncated']}")
                print(f"    Solve Tokens: {results[tier]['output_tokens_solve']}")

            except Exception as e:
                print(f"[{tier.upper()}] Exception: {e}")
                import traceback
                traceback.print_exc()
                results[tier] = {"ok": False, "exception": str(e)}

    print("\n[VERIFICATION SUMMARY]")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(verify_fix())
