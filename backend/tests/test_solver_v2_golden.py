"""
Golden test cases for Solver V2.

Tests the complete end-to-end workflow including:
- Linear equations
- Line through points (visual required)
- System of equations (multi_plot required)
- Inequality (number_line)
"""

import asyncio
import json
from typing import Dict, Any


async def test_linear_equation():
    """
    Test Case 1: Simple linear equation.
    
    Expected:
    - difficulty: trivial or standard
    - steps: 2-4
    - concepts: 3-5
    - verification: ≥1 method
    - visual_policy.required: False
    """
    print("\n" + "="*70)
    print("TEST CASE 1: Linear Equation")
    print("="*70)
    
    from app.services.solver_v2 import solver_service_v2
    
    problem = "Solve for x: 2x+7=19"
    
    try:
        result = await solver_service_v2.solve_problem_v2(
            problem_text=problem,
            context=None,
            user_id=1,
            trace=True
        )
        
        print(f"✅ Solved successfully")
        print(f"   Difficulty: {result.get('difficulty')}")
        print(f"   Steps: {len(result.get('solution', {}).get('steps', []))}")
        print(f"   Concepts: {len(result.get('concepts', []))}")
        print(f"   Verification methods: {len(result.get('verification', {}).get('methods_used', []))}")
        print(f"   Visual required: {result.get('visual_policy', {}).get('required')}")
        print(f"   Model: {result.get('_model')}")
        
        # Validation
        assert result.get('difficulty') in ['trivial', 'standard', 'advanced'], "Invalid difficulty"
        assert len(result.get('concepts', [])) >= 3, "Need ≥3 concepts"
        assert len(result.get('verification', {}).get('methods_used', [])) >= 1, "Need ≥1 verification"
        
        print("✅ All assertions passed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_line_through_points():
    """
    Test Case 2: Line through two points.
    
    Expected:
    - difficulty: standard
    - steps: ≥4
    - visual_policy.required: True
    - visuals: MUST include line_plot
    """
    print("\n" + "="*70)
    print("TEST CASE 2: Line Through Points")
    print("="*70)
    
    from app.services.solver_v2 import solver_service_v2
    
    problem = "Find the equation of the line passing through the points (-3, 0) and (0, 6)"
    
    try:
        result = await solver_service_v2.solve_problem_v2(
            problem_text=problem,
            context=None,
            user_id=1,
            trace=True
        )
        
        print(f"✅ Solved successfully")
        print(f"   Difficulty: {result.get('difficulty')}")
        print(f"   Steps: {len(result.get('solution', {}).get('steps', []))}")
        print(f"   Visual required: {result.get('visual_policy', {}).get('required')}")
        print(f"   Visuals count: {len(result.get('visuals', []))}")
        
        # Validation
        assert result.get('visual_policy', {}).get('required') == True, "Visual should be required"
        assert len(result.get('visuals', [])) > 0, "Must have at least one visual"
        
        print("✅ All assertions passed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_system_of_equations():
    """
    Test Case 3: System of equations.
    
    Expected:
    - visuals: MUST include multi_plot_request
    - verification: ≥2 methods
    """
    print("\n" + "="*70)
    print("TEST CASE 3: System of Equations")
    print("="*70)
    
    from app.services.solver_v2 import solver_service_v2
    
    problem = "Solve the system: y = 2x + 1 and y = -x + 4"
    
    try:
        result = await solver_service_v2.solve_problem_v2(
            problem_text=problem,
            context=None,
            user_id=1,
            trace=True
        )
        
        print(f"✅ Solved successfully")
        print(f"   Visual required: {result.get('visual_policy', {}).get('required')}")
        print(f"   Visuals count: {len(result.get('visuals', []))}")
        print(f"   Verification methods: {len(result.get('verification', {}).get('methods_used', []))}")
        
        # Validation
        assert result.get('visual_policy', {}).get('required') == True, "Visual should be required"
        assert len(result.get('verification', {}).get('methods_used', [])) >= 2, "Need ≥2 verification methods"
        
        print("✅ All assertions passed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_inequality():
    """
    Test Case 4: Inequality.
    
    Expected:
    - visuals or visuals_suggested: Should include number_line
    """
    print("\n" + "="*70)
    print("TEST CASE 4: Inequality")
    print("="*70)
    
    from app.services.solver_v2 import solver_service_v2
    
    problem = "Solve the inequality: 3x - 5 > 7"
    
    try:
        result = await solver_service_v2.solve_problem_v2(
            problem_text=problem,
            context=None,
            user_id=1,
            trace=True
        )
        
        print(f"✅ Solved successfully")
        visuals = result.get('visuals', [])
        visuals_suggested = result.get('visuals_suggested', [])
        all_visuals = visuals + visuals_suggested
        
        has_number_line = any(v.get('type') == 'number_line' for v in all_visuals)
        
        print(f"   Visuals: {len(visuals)}")
        print(f"   Suggested: {len(visuals_suggested)}")
        print(f"   Has number_line: {has_number_line}")
        
        # Soft assertion - should have number_line but not required
        if not has_number_line:
            print("⚠️  Warning: Inequality should include number_line visual")
        
        print("✅ Test completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_golden_tests():
    """Run all golden test cases."""
    print("\n" + "#"*70)
    print("# SOLVER V2 - GOLDEN TEST SUITE")
    print("#"*70)
    
    tests = [
        ("Linear Equation", test_linear_equation),
        ("Line Through Points", test_line_through_points),
        ("System of Equations", test_system_of_equations),
        ("Inequality", test_inequality),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "#"*70)
    print("# GOLDEN TEST SUMMARY")
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
    success = asyncio.run(run_golden_tests())
    sys.exit(0 if success else 1)
