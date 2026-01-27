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

async def main():
    print("Initializing SolverV3...")
    solver = SolverV3()
    
    problem = "A random sample of size 725 is drawn from a large population. The population standard deviation is 1.2. The sample mean is 10.6. Find a 99% confidence interval for the population mean, μ. Round your answers to the nearest tenth."
    print(f"Solving problem: {problem}")
    
    # We pass db_session=None to verify the fallback/standalone logic, 
    # or we could set it up if needed. The fallback I improved should handle None.
    try:
        result = await solver.solve(
            problem_text=problem,
            requested_mode="detailed",
            user_tier="experienced_student" # Force a tier that likely maps to detailed
        )
        
        output_file = "solve_output.txt"
        print(f"Saving output to {output_file}...")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2))
            
        print("Done.")
        
        # Also print a summary to console
        if result.get("error"):
            print("ERROR RETURNED:")
            print(result.get("message"))
        else:
            final_answer = result.get("final_answer", {}).get("answer_text", "N/A")
            print(f"Final Answer: {final_answer}")
            print(f"Telemetry: {json.dumps(result.get('telemetry'), indent=2)}")

    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
