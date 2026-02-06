"""
Test the solver with research tier to verify console logging.
"""
import asyncio
import os
import sys

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Now import after env is loaded
from sqlmodel import Session
from app.database import engine
from app.services.solver_v3 import get_solver_v3

async def main():
    print("\n" + "="*60)
    print("STARTING RESEARCH TIER TEST")
    print("="*60 + "\n", flush=True)
    
    problem = "Find and classify the critical points of f(x) = x^3 - 3x + ln(x) on its domain."
    
    with Session(engine) as session:
        solver = get_solver_v3()
        
        print(f"\n[TEST] Calling solver.solve() with research tier...\n", flush=True)
        
        result = await solver.solve(
            problem_text=problem,
            context="",
            trace=True,
            request_id="TEST-RESEARCH-001",
            user_tier="research",
            requested_mode="detailed",
            db_session=session,
        )
        
        print("\n" + "="*60)
        print("RESULT SUMMARY")
        print("="*60)
        
        if "error" in result or result.get("_content", {}).get("status") == "error":
            print(f"ERROR: {result.get('error') or result.get('_telemetry', {})}")
        else:
            print(f"Status: SUCCESS")
            print(f"Mode: {result.get('telemetry', {}).get('mode_resolved')}")
            print(f"Tier: {result.get('telemetry', {}).get('tier_effective')}")
            print(f"Latency: {result.get('telemetry', {}).get('latency_ms_total')}ms")

if __name__ == "__main__":
    asyncio.run(main())
