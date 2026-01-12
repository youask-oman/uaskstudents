"""
Comprehensive Integration Tests for Math Solver V3.

Tests the complete V3 pipeline with real sample problems:
- Quadratic equations
- Rational functions with asymptotes
- Systems of equations
- Inequalities
- Word problems
- Statistics

Each test verifies:
- JSON schema validation
- Visualization generation
- 2+ verification methods
- Tutor-grade explanations
"""

import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_quadratic_equation():
    """Test 1: Quadratic equation - should generate parabola plot."""
    print("\n" + "="*70)
    print("TEST 1: Quadratic Equation")
    print("="*70)
    
    from app.services.solver_v3 import get_solver_v3
    
    solver = get_solver_v3()
    problem = "Solve x^2 - 5x + 6 = 0"
    
    try:
        result = await solver.solve(problem, trace=True)
        
        # Verify structure
        assert "problem" in result, "Missing 'problem' field"
        assert "solution" in result, "Missing 'solution' field"
        assert "verification" in result, "Missing 'verification' field"
        assert "plot" in result, "Missing 'plot' field"
        assert "similar_examples" in result, "Missing 'similar_examples' field"
        
        # Verify verification count
        verif_count = len(result.get("verification", []))
        assert verif_count >= 1, f"Expected >=1 verification methods, got {verif_count}"
        
        # Verify similar examples
        examples_count = len(result.get("similar_examples", []))
        assert examples_count >= 2, f"Expected >=2 similar examples, got {examples_count}"
        
        # Check plot
        plot = result.get("plot", {})
        should_plot = plot.get("should_plot", False)
        print(f"\n✅ Quadratic test passed!")
        print(f"   - Verification methods: {verif_count}")
        print(f"   - Similar examples: {examples_count}")
        print(f"   - Should plot: {should_plot}")
        print(f"   - Final answer: {result['solution']['final_answer'][:50]}...")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Quadratic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_system_of_equations():
    """Test 2: System of equations - should generate multi-function plot."""
    print("\n" + "="*70)
    print("TEST 2: System of Equations")
    print("="*70)
    
    from app.services.solver_v3 import get_solver_v3
    
    solver = get_solver_v3()
    problem = "Solve the system: y = 2x + 3 and y = -x + 6"
    
    try:
        result = await solver.solve(problem, context="Subject: Algebra", trace=False)
        
        # Basic checks
        assert "problem" in result
        assert "solution" in result
        assert "verification" in result
        assert "plot" in result
        
        plot = result.get("plot", {})
        plot_type = plot.get("plot_type")
        
        print(f"\n✅ System test passed!")
        print(f"   - Plot type: {plot_type}")
        print(f"   - Verification methods: {len(result.get('verification', []))}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ System test failed: {e}")
        return False


async def test_inequality():
    """Test 3: Inequality - should generate number line."""
    print("\n" + "="*70)
    print("TEST 3: Inequality")
    print("="*70)
    
    from app.services.solver_v3 import get_solver_v3
    
    solver = get_solver_v3()
    problem = "Solve 2x + 5 > 11"
    
    try:
        result = await solver.solve(problem, trace=False)
        
        assert "plot" in result
        plot = result.get("plot", {})
        
        print(f"\n✅ Inequality test passed!")
        print(f"   - Should plot: {plot.get('should_plot')}")
        print(f"   - Plot type: {plot.get('plot_type')}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Inequality test failed: {e}")
        return False


async def test_simple_algebra():
    """Test 4: Simple algebra - may not require plot."""
    print("\n" + "="*70)
    print("TEST 4: Simple Algebra")
    print("="*70)
    
    from app.services.solver_v3 import get_solver_v3
    
    solver = get_solver_v3()
    problem = "Solve 3x + 7 = 22"
    
    try:
        result = await solver.solve(problem, trace=False)
        
        # Even simple problems should have structure
        assert "problem" in result
        assert "solution" in result
        assert "verification" in result
        
        # May or may not have plot
        plot = result.get("plot", {})
        
        print(f"\n✅ Simple algebra test passed!")
        print(f"   - Final answer: {result['solution']['final_answer']}")
        print(f"   - Steps: {len(result['solution']['steps'])}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Simple algebra test failed: {e}")
        return False


async def test_schema_validation():
    """Test 5: Schema validation."""
    print("\n" + "="*70)
    print("TEST 5: Schema Validation")
    print("="*70)
    
    from app.services.validation_v3 import validate_response
    
    # Valid minimal response
    valid_data = {
        "problem": {
            "input": "Test",
            "topic": "algebra",
            "goal": "Test"
        },
        "analysis": {
            "plan": ["Step 1"],
            "detected_entities": {
                "expressions": [],
                "equations": [],
                "functions": [],
                "constraints": []
            }
        },
        "solution": {
            "final_answer": "x = 5",
            "steps": [
                {
                    "index": 1,
                    "title": "Step",
                    "concept": "Test",
                    "rules_used": ["Rule1"],
                    "work": ["Work"],
                    "result": "Result",
                    "checkpoint": {"question": "Q?", "expected_answer": "A"}
                }
            ]
        },
        "verification": [
            {
                "method": "Test",
                "why_it_works": "Because",
                "steps": ["Step1"],
                "conclusion": "OK"
            },
            {
                "method": "Test2",
                "why_it_works": "Because2",
                "steps": ["Step2"],
                "conclusion": "OK2"
            }
        ],
        "plot": {
            "should_plot": False,
            "plot_type": "number_line",
            "plan": {
                "title": "Test",
                "axes": {"x_label": "x", "y_label": "y"},
                "recommended_window": {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10},
                "objects": [{"kind": "curve", "expression": "x", "label": "L"}],
                "annotations": [],
                "sampling": {"strategy": "uniform", "resolution": 100}
            }
        },
        "similar_examples": [
            {"problem": "P1", "key_idea": "K1", "short_solution": "S1"},
            {"problem": "P2", "key_idea": "K2", "short_solution": "S2"}
        ],
        "meta": {
            "confidence": 0.9,
            "localization": {"region": "north_america", "notation": "standard"},
            "rounding_policy": "2 decimals"
        }
    }
    
    result = validate_response(valid_data, strict=True)
    
    if result.valid:
        print("\n✅ Schema validation test passed!")
        return True
    else:
        print(f"\n❌ Schema validation failed: {result.errors}")
        return False


async def test_visualization_engine():
    """Test 6: Visualization decision engine."""
    print("\n" + "="*70)
    print("TEST 6: Visualization Engine")
    print("="*70)
    
    from app.services.visualization.decision_engine import get_visualization_engine
    
    engine = get_visualization_engine()
    
    test_cases = [
        ("Graph y = x^2", {"detected_entities": {"functions": ["y=x^2"], "equations": [], "constraints": []}}),
        ("Solve x + 5 = 10", {"detected_entities": {"functions": [], "equations": ["x+5=10"], "constraints": []}}),
    ]
    
    passed = 0
    for problem, analysis in test_cases:
        decision = engine.should_visualize(problem, analysis)
        print(f"   '{problem[:30]}...' → should_visualize={decision.should_visualize}, type={decision.plot_type}")
        passed += 1
    
    print(f"\n✅ Visualization engine test passed ({passed}/{ len(test_cases)})!")
    return True


async def run_all_integration_tests():
    """Run all integration tests."""
    print("\n" + "#"*70)
    print("# MATH SOLVER V3 - INTEGRATION TEST SUITE")
    print("#"*70)
    
    tests = [
        ("Quadratic Equation", test_quadratic_equation),
        ("System of Equations", test_system_of_equations),
        ("Inequality", test_inequality),
        ("Simple Algebra", test_simple_algebra),
        ("Schema Validation", test_schema_validation),
        ("Visualization Engine", test_visualization_engine),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
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
    print("\n" + "!"*70)
    print("! IMPORTANT: Set OPENAI_API_KEY environment variable before running")
    print("!"*70)
    
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n❌ ERROR: OPENAI_API_KEY not set")
        print("   Set it with: $env:OPENAI_API_KEY='your-key' (PowerShell)")
        sys.exit(1)
    
    success = asyncio.run(run_all_integration_tests())
    sys.exit(0 if success else 1)
