import sys
import json
import asyncio
import os
import traceback

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.database import engine
from sqlmodel import Session, select
from app.services.solver_v3 import get_solver_v3
from app.models import SystemConfig

async def main():
    print("Initializing Solver V3...")
    try:
        s = get_solver_v3()
        
        with Session(engine) as session:
            row = session.get(SystemConfig, "active_llm_provider")
            print(f"SystemConfig active_llm_provider: {row.value if row else 'None'}")
            
            print("Running solver.solve_stream for standard tier...")
            full_text = ""
            last_telemetry = None
            
            try:
                async for chunk in s.solve_stream(
                    problem_text="Solve x+1=2",
                    db_session=session,
                    trace=True
                ):
                    print(f"Chunk received: {chunk.get('type')}")
                    if chunk["type"] == "delta":
                        full_text += chunk["text"]
                    elif chunk["type"] == "usage":
                        last_telemetry = chunk["telemetry"]
                    elif chunk["type"] == "failure":
                        print(f"FAILURE CHUNK: {chunk.get('error')}")
                    elif chunk["type"] == "error":
                        print(f"ERROR CHUNK: {chunk.get('error')}")
            except Exception as e:
                print(f"Stream iteration failed: {e}")
                traceback.print_exc()
            
            print("--- FINAL RESULT ---")
            if last_telemetry:
                print(f"Resolved Provider: {last_telemetry.get('provider')}")
                print(f"Model Used: {last_telemetry.get('model')}")
            else:
                print("No telemetry chunk received.")
            
            print(f"Content Length: {len(full_text)}")
            if len(full_text) > 0:
                print(f"Preview: {full_text[:100]}...")
    except Exception as e:
        print(f"Main failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
