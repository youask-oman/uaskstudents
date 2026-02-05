
import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Ensure we can import app modules
sys.path.append(os.path.join(os.getcwd(), "backend"))

load_dotenv()

from app.services.solver_v3 import get_solver_v3
from app.services.llm.manager import get_llm_manager
from sqlmodel import Session
from app.database import engine

async def run_comparison():
    print("Initializing SolverV3...")
    get_llm_manager()
    solver = get_solver_v3()
    
    problem = r"Simplify \frac{2x^3y^{2}}{4xy}"
    context = "cosider Graph Mode = on"
    
    tiers_to_test = ["standard", "research"]
    results = {}

    with Session(engine) as session:
        for tier in tiers_to_test:
            print(f"\n[TESTING TIER: {tier.upper()}]")
            try:
                response = await solver.solve(
                    problem_text=problem,
                    context=context,
                    trace=True,
                    requested_mode="minimal",
                    user_tier=tier,
                    db_session=session
                )
                
                results[tier] = {
                    "ok": not response.get("error"),
                    "error": response.get("error"),
                    "error_message": response.get("message"),
                    "output_tokens": response.get("_telemetry", {}).get("output_tokens"),
                    "usage": response.get("_telemetry", {}).get("openai_payload", {}).get("max_output_tokens"),
                    "finish_reason": response.get("_telemetry", {}).get("status_checks", [{}])[0].get("finish_reason")
                }
                
                # Save raw responses
                with open(f"backend/response_{tier}.json", "w", encoding="utf-8") as f:
                    json.dump(response, f, indent=2)
                
                if "_telemetry" in response:
                    with open(f"backend/telemetry_{tier}.json", "w", encoding="utf-8") as f:
                        json.dump(response["_telemetry"], f, indent=2)

                print(f"[{tier.upper()}] Result: {'SUCCESS' if results[tier]['ok'] else 'FAILURE'}")
                if not results[tier]['ok']:
                    print(f"Error: {results[tier]['error_message']}")

            except Exception as e:
                print(f"[{tier.upper()}] Exception: {e}")
                results[tier] = {"ok": False, "exception": str(e)}

    print("\n[COMPARISON SUMMARY]")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(run_comparison())
