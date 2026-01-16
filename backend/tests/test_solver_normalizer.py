import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, AsyncMock, patch
from app.services.solver_v3 import get_solver_v3

async def test_normalizer():
    # Set dummy API key to avoid init errors
    os.environ["OPENAI_API_KEY"] = "sk-dummy"
    
    solver = get_solver_v3()
    
    # Mock LLM response: missing refusal, quality, and verification.alternative_method
    incomplete_data = {
        "problem": {"original_text": "x=1", "normalized_text": "x=1"},
        "classification": {"topic": "Algebra", "difficulty": "Easy", "detected_tasks": ["Solve"]},
        "assumptions": [],
        "steps": [{"index": 1, "title": "Step 1", "explanation": "Explain", "math_latex": "x=1", "rules_used": []}],
        "final_answer": {"answer_text": "x=1"},
        "verification": {"method": "Check", "work_latex": "x=1", "conclusion": "Good"}, # Missing alternative_method
        # Missing visuals
        # Missing refusal
        # Missing quality
    }
    
    print("Testing Normalizer with incomplete data...")
    
    # Patch _call_llm_with_schema
    with patch.object(solver, '_call_llm_with_schema', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = (incomplete_data, {"input": 10, "output": 10})
        
        # Also patch get_prompt to allow execution
        with patch('app.services.solver_v3.get_prompt', return_value="System Prompt"):
             result = await solver.solve("x=1")
             
    # Assertions
    print("\n--- Test Results ---")
    telemetry = result.get("_telemetry", {})
    val_fails = telemetry.get('validation_failures_count')
    repaired = telemetry.get('repaired')
    
    print(f"Validation Failures: {val_fails}")
    print(f"Repaired: {repaired}")
    
    all_passed = True
    
    if val_fails == 0 and not repaired:
        print("✅ SUCCESS: Loop reported no validation errors.")
    else:
        print("❌ FAILURE: Validation failed (repair triggered).")
        all_passed = False
        
    # Check keys
    if "refusal" in result:
        print(f"✅ Refusal key injected: {result['refusal']}")
    else:
        print("❌ Refusal key MISSING")
        all_passed = False

    if "quality" in result:
        print(f"✅ Quality key injected: {result['quality']}")
    else:
        print("❌ Quality key MISSING")
        all_passed = False

    if "visuals" in result:
        print(f"✅ Visuals key injected: {result['visuals']}")
    else:
        print("❌ Visuals key MISSING")
        all_passed = False
        
    verif = result.get("verification", {})
    if "alternative_method" in verif:
        print(f"✅ Verification.alternative_method injected: {verif['alternative_method']}")
    else:
        print("❌ Verification.alternative_method MISSING")
        all_passed = False

    if all_passed:
        print("\nSUMMARY: Normalizer Logic Verified.")
    else:
        print("\nSUMMARY: Normalizer Logic FAILED.")

if __name__ == "__main__":
    asyncio.run(test_normalizer())
