
import asyncio
import json
import uuid
import sys
import os
from dotenv import load_dotenv

# Add root backend dir to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env explicitly
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)

# Verify key presence
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in environment")
if not os.getenv("OPENAI_MODEL_DEFAULT"):
    print("WARNING: OPENAI_MODEL_DEFAULT not found, setting default")
    os.environ["OPENAI_MODEL_DEFAULT"] = "gpt-4o"


from app.services.solver_v3 import get_solver_v3
from sqlmodel import Session, create_engine, select

# Use local sqlite DB
DATABASE_URL = "sqlite:///./uaskstudents.db" 
engine = create_engine(DATABASE_URL)

async def test_real_solve():
    print("Initializing SolverV3...")
    solver = get_solver_v3()
    
    # 1. Setup Request
    request_id = str(uuid.uuid4())
    problem_text = """
    Fourier Series & Gibbs Phenomenon: Convergence, Overshoot, and Spectral Decay
    Topic: Fourier analysis, approximation theory, convergence in norms, spectral interpretation.

    Problem:
    Let f(x) be the 2π-periodic extension of the square wave
      f(x) = 1  for x ∈ (0, π),
      f(x) = -1 for x ∈ (-π, 0).
    Let S_N(x) be the N-term Fourier partial sum of f.

    Tasks (plot required in at least three distinct steps):
    (a) For N ∈ {5, 15, 50, 200}, plot f(x) and S_N(x) over [-π, π] on the same axes. Use the plots to measure overshoot near discontinuities and describe the Gibbs phenomenon.
    (b) For the same N, plot the pointwise error |S_N(x) - f(x)| over [-π, π]. Then create a zoomed-in plot near x = 0 to show how the overshoot region shrinks while the overshoot height persists.
    (c) Plot the magnitudes of Fourier coefficients |f̂(n)| versus n on log-log axes. Fit an approximate slope and relate it to the regularity (discontinuity) of f.
    (d) Plot convergence metrics: compute and plot ||S_N - f||_{L^2} vs N and (separately) ||S_N - f||_{L∞} away from discontinuities vs N. Explain why the observed rates differ.

    Optional extension:
    (e) Replace S_N with Fejér sums σ_N(x). Plot σ_N versus S_N for the same N and compare overshoot and uniform convergence behavior.
    """
    
    print(f"Starting REAL solve request (ID: {request_id})...")
    print("Streaming response chunks...")

    full_text = ""
    chunk_count = 0
    
    with Session(engine) as session:
        # Load binding for 'standard' tier
        print("Loading prompt binding from REAL DB...")
        from app.prompts.db_loader import load_prompt_bundle
        
        # Try lowercase 'standard' first, if fails try 'STANDARD'
        try:
            binding = load_prompt_bundle(tier="standard", mode="solve", session=session)
        except Exception:
            print("Retrying with tier='STANDARD'")
            binding = load_prompt_bundle(tier="STANDARD", mode="SOLVE", session=session)
        
        system_prompt = binding["system_prompt"]
        schema_config = binding["schema"]
        
        # Use binding's max_tokens if available (it might be in metadata or config), 
        # otherwise default to high value as verified.
        # The prompt binding schema usually doesn't store max_tokens directly in V3 unless in config.
        # But we ensure it is HIGH here as per fix.
        MAX_TOKENS = 6000
        
        # Wrapper logic
        from app.utils.schema_deref import deref_json_schema
        from app.utils.schema_cleaner import enforce_strict

        def prepare_schema(config_schema):
             if "schema" in config_schema:
                 candidate = config_schema["schema"]
             else:
                 candidate = config_schema
            
             deref = deref_json_schema(candidate)
             deref = enforce_strict(deref)
             if deref.get("type") is None:
                 deref["type"] = "object"
                 
             return {
                 "name": "solve_response_v3",
                 "strict": True,
                 "schema": deref
             }

        openai_schema = prepare_schema(schema_config)
        
        print(f"Schema prepared (keys: {list(openai_schema.keys())})")
        
        stream = solver.solve_stream(
            problem_text=problem_text,
            context="",
            trace=True,
            request_id=request_id,
            max_output_tokens=MAX_TOKENS,
            system_prompt=system_prompt,
            developer_prompt=binding.get("developer_prompt"),
            json_schema_config=openai_schema,
            requested_mode="detailed"
        )
        
        async for chunk in stream:
            chunk_count += 1
            if chunk.get("type") == "delta":
                text = chunk.get("text", "")
                full_text += text
                # We do NOT parse here. We just accumulate.
                if len(full_text) % 100 < len(text):
                    print(".", end="", flush=True)
            elif chunk.get("type") == "error":
                print(f"\nSTREAM ERROR: {chunk}")
            
        print("\nStream complete.")
        print(f"Total Length: {len(full_text)}")
        
        # Now validate the result using our safe parser
        print("Validating accumulated JSON...")
        from app.utils.safe_json import safe_parse_json
        
        try:
            data = safe_parse_json(full_text)
            print("SUCCESS: JSON parsed correctly.")
            # Verify keys
            keys = list(data.keys())
            print(f"Root keys: {keys}")
            if "steps" in keys and "final_answer" in keys:
                 print("Structure looks valid.")
            else:
                 print("WARNING: Missing key fields.")
                 
        except Exception as e:
            print(f"FAILURE: JSON parsing failed: {e}")
            print(f"Tail: {full_text[-500:]}")

if __name__ == "__main__":
    asyncio.run(test_real_solve())
