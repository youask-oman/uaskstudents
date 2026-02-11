"""
Complete 3-Tier Test with Full Output Logging
Problem: Find the inverse of f(x) = (x-1)/(x+2)
"""

import os
import sys
import json
import asyncio
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from sqlmodel import Session

from app.database import engine
from app.models import PromptModeEnum
from app.prompts.db_loader import resolve_prompt_bundle

PROBLEM = r"Find the inverse of f(x) = \frac{x - 1}{x + 2}"

async def test_tier(tier: str, client: AsyncOpenAI, all_results: dict):
    """Test a single tier with full logging."""
    print(f"\n{'='*60}")
    print(f"TESTING TIER: {tier}")
    print(f"Problem: {PROBLEM}")
    print('='*60)
    
    results = {
        "tier": tier,
        "problem": PROBLEM,
        "timestamp": datetime.now().isoformat(),
        "solve": None,
        "plot_trigger": None,
        "plot_spec": None
    }
    
    with Session(engine) as session:
        # SOLVE
        print(f"\n[SOLVE - {tier}]")
        try:
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.SOLVE,
                db_session=session,
            )
            
            messages = [
                {"role": "system", "content": bundle.system_prompt_content},
                {"role": "developer", "content": bundle.developer_prompt_content},
                {"role": "user", "content": PROBLEM}
            ]
            
            # Get schema wrapper and sanitize
            db_wrapper = bundle.output_schema_json or {}
            inner_schema = db_wrapper.get("schema", {})
            
            # Simple sanitization
            def sanitize(obj):
                if isinstance(obj, dict):
                    result = {}
                    for k, v in obj.items():
                        if k in ('allOf', 'if', 'then', 'else'):
                            continue
                        if k == 'description' and '$ref' in obj:
                            continue
                        result[k] = sanitize(v)
                    if 'properties' in result:
                        props = set(result['properties'].keys())
                        req = set(result.get('required', []))
                        result['required'] = list(props | req)
                        if 'type' not in result:
                            result['type'] = 'object'
                    return result
                elif isinstance(obj, list):
                    return [sanitize(item) for item in obj]
                return obj
            
            sanitized_schema = sanitize(inner_schema)
            
            request_payload = {
                "model": "gpt-5-mini",
                "messages": messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": db_wrapper.get("name", "solve_output"),
                        "strict": db_wrapper.get("strict", True),
                        "schema": sanitized_schema
                    }
                }
            }
            
            start = time.time()
            response = await client.chat.completions.create(**request_payload)
            latency = (time.time() - start) * 1000
            
            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)
            
            results["solve"] = {
                "success": True,
                "request_id": response.id,
                "latency_ms": latency,
                "tokens_in": response.usage.prompt_tokens if response.usage else 0,
                "tokens_out": response.usage.completion_tokens if response.usage else 0,
                "system_prompt": bundle.global_system_prompt_id,
                "developer_prompt": bundle.developer_prompt_id,
                "schema": bundle.output_schema_id,
                "raw_request": request_payload,
                "raw_response": raw_content,
                "parsed_result": result,
                "final_answer": result.get("final_answer", {}).get("latex", "N/A")
            }
            
            print(f"✅ Solve SUCCESS")
            print(f"   Request ID: {response.id}")
            print(f"   Latency: {latency:.0f}ms")
            print(f"   Tokens: {results['solve']['tokens_in']} → {results['solve']['tokens_out']}")
            print(f"   Final Answer: {results['solve']['final_answer'][:100]}")
            
        except Exception as e:
            results["solve"] = {"success": False, "error": str(e)}
            print(f"❌ Solve FAILED: {e}")
    
    all_results[tier] = results
    return results

async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)
    
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    all_results = {}
    
    for tier in ["FREE", "STANDARD", "RESEARCH"]:
        await test_tier(tier, client, all_results)
    
    # Save all results
    output_file = "inverse_function_full_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"FULL RESULTS SAVED TO: {output_file}")
    print('='*60)
    
    # Print summary
    print("\nSUMMARY:")
    for tier, res in all_results.items():
        solve = res.get("solve", {})
        status = "✅" if solve.get("success") else "❌"
        print(f"{status} {tier}: {solve.get('final_answer', 'FAILED')[:50]}")

if __name__ == "__main__":
    asyncio.run(main())
