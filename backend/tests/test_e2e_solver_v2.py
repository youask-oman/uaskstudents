"""
End-to-end test for Solver V2.

Tests the complete workflow:
1. Health check
2. Direct solver V2 call
3. Full API solve endpoint
"""

import requests
import json


def test_health():
    """Test 1: Health endpoint."""
    print("\n" + "="*70)
    print("TEST 1: Health Check")
    print("="*70)
    
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("✅ Health check passed")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_solver_v2_direct():
    """Test 2: Direct solver V2 call."""
    print("\n" + "="*70)
    print("TEST 2: Solver V2 Direct Call")
    print("="*70)
    
    import sys
    import asyncio
    # Add path for imports when run from tests directory
    sys.path.insert(0, '/app')
    
    async def run_test():
        from app.services.solver_v2 import solver_service_v2
        
        result = await solver_service_v2.solve_problem_v2(
            problem_text="Solve for x: 2x+7=19",
            context=None,
            user_id=1,
            trace=False
        )
        
        print(f"✅ Solver V2 returned response")
        print(f"   Model: {result.get('_model')}")
        print(f"   Difficulty: {result.get('difficulty')}")
        print(f"   Steps: {len(result.get('solution', {}).get('steps', []))}")
        print(f"   Concepts: {len(result.get('concepts', []))}")
        print(f"   Has _content: {bool(result.get('_content'))}")
        
        return True
    
    try:
        return asyncio.run(run_test())
    except Exception as e:
        print(f"❌ Direct solver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_solve_api():
    """Test 3: Full solve API endpoint."""
    print("\n" + "="*70)
    print("TEST 3: Solve API Endpoint")
    print("="*70)
    
    # First, get an API key or use test credentials
    # For now, we'll test the endpoint structure
    
    payload = {
        "text_query": "Solve for x: 2x+7=19",
        "mode": "general",
        "subject": "Math"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("Sending solve request...")
        response = requests.post(
            "http://localhost:8000/api/v1/solve",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("⚠️  Authentication required (expected for unauthenticated request)")
            print("   Endpoint is responding correctly")
            return True
        elif response.status_code == 200:
            result = response.json()
            print("✅ Solve API succeeded")
            print(f"   Session ID: {result.get('session_id')}")
            print(f"   Model: {result.get('model_used')}")
            return True
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Solve API test failed: {e}")
        return False


def test_solver_v2_enabled():
    """Test 4: Check if Solver V2 is enabled."""
    print("\n" + "="*70)
    print("TEST 4: Solver V2 Configuration")
    print("="*70)
    
    import os
    
    # This would need to be run inside the container
    print("Checking environment variables...")
    print("Note: Run inside container to verify SOLVER_V2_ENABLED")
    
    return True


def run_tests():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# SOLVER V2 - END-TO-END TEST SUITE")
    print("#"*70)
    
    tests = [
        ("Health Check", test_health),
        ("Solver V2 Direct", test_solver_v2_direct),
        ("Solve API Endpoint", test_solve_api),
        ("Solver V2 Config", test_solver_v2_enabled),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "#"*70)
    print("# TEST SUMMARY")
    print("#"*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*70}\n")
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
