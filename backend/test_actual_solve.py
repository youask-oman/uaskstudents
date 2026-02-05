"""
Test script that calls the ACTUAL solve endpoint directly
Problem: \\text{Simplify } \\frac{2x^3y^{2}}{4xy}
Tests all 3 tiers: FREE, STANDARD, RESEARCH
"""

import asyncio
import httpx
import json
import sys
import time
from datetime import datetime

# The actual problem
PROBLEM = r"\text{Simplify } \frac{2x^3y^{2}}{4xy}"

BASE_URL = "http://localhost:8000"
USER_ID = 1

async def test_tier(tier: str):
    """Test solve for a specific tier using the actual API"""
    print(f"\n{'='*60}")
    print(f"TESTING TIER: {tier}")
    print(f"Problem: {PROBLEM}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Call the actual solve_v3_stream endpoint
            response = await client.post(
                f"{BASE_URL}/api/v1/solve_v3_stream",
                params={"user_id": USER_ID},
                json={
                    "confirmed_text": PROBLEM,
                    "requested_mode": "minimal" if tier == "FREE" else "detailed",
                    "tier": tier.lower(),
                    "trusted_context": {
                        "learning_mode": "solve",
                        "grade_level": None,
                        "region_country": None,
                        "region_state_province": None
                    },
                    "features_used": {
                        "ocr_used": False,
                        "voice_used": False,
                        "plot_requested": False
                    },
                    "graph_mode": "auto",
                    "attach_to_step_id": None
                }
            )
            
            elapsed = time.time() - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {elapsed:.2f}s")
            
            if response.status_code == 200:
                # Parse SSE stream
                content = response.text
                print(f"\nResponse length: {len(content)} chars")
                
                # Look for key events in the stream
                if "event: done" in content:
                    # Extract the done event data
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip() == "event: done":
                            if i + 1 < len(lines) and lines[i + 1].startswith("data: "):
                                data = lines[i + 1][6:]  # Remove "data: " prefix
                                try:
                                    done_data = json.loads(data)
                                    print(f"\nDone Event: {json.dumps(done_data, indent=2)}")
                                    
                                    if done_data.get("ok"):
                                        print(f"\n✅ SUCCESS - Tier {tier}")
                                        print(f"Session ID: {done_data.get('session_id')}")
                                        return True
                                    else:
                                        print(f"\n❌ FAILED - Tier {tier}")
                                        print(f"Error: {done_data.get('error', {}).get('message', 'Unknown')}")
                                        return False
                                except json.JSONDecodeError as e:
                                    print(f"Failed to parse done event: {e}")
                                    return False
                else:
                    print("\n❌ No 'done' event found in response")
                    # Print last 500 chars for debugging
                    print(f"Last 500 chars:\n{content[-500:]}")
                    return False
            else:
                print(f"\n❌ HTTP ERROR - Tier {tier}")
                print(f"Response: {response.text[:500]}")
                return False
                
    except httpx.ConnectError:
        print(f"\n❌ CONNECTION ERROR: Backend not running at {BASE_URL}")
        print("Start backend with: uvicorn app.main:app --port 8000")
        return False
    except Exception as e:
        print(f"\n❌ EXCEPTION - Tier {tier}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run tests for all three tiers"""
    print("="*60)
    print("ACTUAL APPLICATION TEST - Solve Endpoint")
    print("Problem: Simplify 2x³y² / 4xy")
    print(f"Started at: {datetime.now().isoformat()}")
    print("="*60)
    
    tiers = ["FREE", "STANDARD", "RESEARCH"]
    results = {}
    
    for tier in tiers:
        results[tier] = await test_tier(tier)
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    for tier, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{tier}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
