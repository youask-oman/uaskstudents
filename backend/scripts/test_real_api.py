"""
Real API Test: Calls the running backend at localhost:8000
Accumulates ONLY text deltas from SSE stream, validates final JSON.
"""
import httpx
import json
import asyncio
import uuid

API_BASE = "http://127.0.0.1:8000"

PROBLEM_TEXT = """
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

async def test_real_api():
    request_id = str(uuid.uuid4())
    print(f"[TEST] Request ID: {request_id}")
    print(f"[TEST] Problem: {PROBLEM_TEXT[:100]}...")
    
    # Build request payload matching /api/v1/solve_v3_stream endpoint
    payload = {
        "text_query": PROBLEM_TEXT,
        "context": "",
        "mode": "detailed",
        "learning_mode": "solve",
        "subject": "math",
        "tier": "standard"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        # Add auth header if needed - assuming dev mode allows anonymous
    }
    
    json_text = ""  # Buffer for ONLY assistant text deltas
    chunk_count = 0
    meta_received = False
    done_received = False
    errors = []
    
    print("[TEST] Connecting to SSE stream...")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Use user_id=1 (assuming dev user) and correct endpoint
        async with client.stream(
            "POST",
            f"{API_BASE}/api/v1/solve_v3_stream?user_id=1",
            json=payload,
            headers=headers
        ) as response:
            print(f"[TEST] Response status: {response.status_code}")
            
            if response.status_code != 200:
                body = await response.aread()
                print(f"[TEST] ERROR: {body.decode()}")
                return
            
            # Parse SSE stream
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                
                # SSE format: "event: <type>\n" or "data: <json>\n"
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                    continue
                
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError as e:
                        print(f"[TEST] SSE parse error: {e} for line: {data_str[:100]}")
                        continue
                    
                    chunk_type = data.get("type")
                    
                    if chunk_type == "delta":
                        # ACCUMULATE ONLY TEXT DELTAS
                        text = data.get("text", "")
                        json_text += text
                        chunk_count += 1
                        if chunk_count % 20 == 0:
                            print(".", end="", flush=True)
                    
                    elif chunk_type == "meta":
                        meta_received = True
                        print(f"\n[TEST] Meta received: request_id={data.get('request_id')}")
                        print(f"[TEST] Meta schema: {data.get('output_schema_id')}")
                        print(f"[TEST] Meta tier: {data.get('tier_requested')} -> {data.get('effective_tier')}")
                        print(f"[TEST] Meta max_tokens: {data.get('max_output_tokens')}")
                        print(f"[TEST] debug_profile_max: {data.get('debug_profile_max')}")
                        print(f"[TEST] debug_policy_limit: {data.get('debug_policy_limit')}")
                        print(f"[TEST] debug_policy_dump: {data.get('debug_policy_dump')}")
                        print(f"[TEST] learning_mode: {data.get('learning_mode')}")
                    
                    elif chunk_type == "done":
                        done_received = True
                        ok = data.get("ok", False)
                        print(f"\n[TEST] Done received: ok={ok}")
                        if not ok:
                            errors.append(data.get("error", "Unknown error"))
                    
                    elif chunk_type == "stage":
                        stage_name = data.get("name", "")
                        print(f"\n[TEST] Stage: {stage_name}")
                    
                    elif chunk_type == "error":
                        errors.append(data.get("error", data))
                        print(f"\n[TEST] Stream error: {data}")
    
    print(f"\n[TEST] Stream complete. Chunks: {chunk_count}, Length: {len(json_text)}")

    # Save raw output for inspection
    with open("openai_raw_output.json", "w", encoding="utf-8") as f:
        f.write(json_text)
    print(f"[TEST] Saved raw output to openai_raw_output.json")
    
    if errors:
        print(f"[TEST] ERRORS: {errors}")
    
    # NOW validate the accumulated JSON (only after stream is complete)
    print("[TEST] Validating accumulated JSON...")
    
    if not json_text.strip():
        print("[TEST] FAILURE: Empty json_text buffer")
        return
    
    # Use the backend's safe_parse_json if available, else json.loads
    try:
        import sys, os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from app.utils.safe_json import safe_parse_json
        data = safe_parse_json(json_text)
        print("[TEST] SUCCESS: JSON parsed via safe_parse_json")
    except ImportError:
        data = json.loads(json_text)
        print("[TEST] SUCCESS: JSON parsed via json.loads")
    except Exception as e:
        print(f"[TEST] FAILURE: Parse error: {e}")
        # Save to file for inspection
        with open("failed_output.txt", "w", encoding="utf-8") as f:
            f.write(json_text)
        print(f"[TEST] Saved failed output to failed_output.txt")
        return
    
    # Verify structure
    keys = list(data.keys())
    print(f"[TEST] Root keys: {keys}")
    
    required = ["schema_version", "steps", "final_answer"]
    missing = [k for k in required if k not in keys]
    if missing:
        print(f"[TEST] WARNING: Missing keys: {missing}")
    else:
        print("[TEST] All required keys present!")
    
    # Print summary
    steps = data.get("steps", [])
    print(f"[TEST] Steps count: {len(steps)}")
    final = data.get("final_answer", {})
    print(f"[TEST] Final answer preview: {str(final.get('answer_text', ''))[:200]}...")
    
    print("\n[TEST] === FULL SUCCESS ===")

if __name__ == "__main__":
    asyncio.run(test_real_api())
