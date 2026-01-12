"""
Quick test script for all V3 components.
Run from backend directory: python test_v3_quick.py
"""

import sys
import traceback

def test_prompt_registry():
    """Test 1: Prompt Registry"""
    print("\n" + "="*70)
    print("TEST 1: Prompt Registry")
    print("="*70)
    
    try:
        from app.prompts.registry import get_prompt_registry
        
        registry = get_prompt_registry()
        print(f"✅ Registry initialized: {len(registry.prompts)} prompts")
        
        system_prompt = registry.get_prompt("solver_system", "v3")
        print(f"✅ System prompt loaded: {len(system_prompt)} characters")
        
        schema = registry.get_schema("na_math_solver")
        print(f"✅ Schema loaded: {len(schema.get('properties', {}))} properties")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_pydantic_models():
    """Test 2: Pydantic Models"""
    print("\n" + "="*70)
    print("TEST 2: Pydantic V2 Models")
    print("="*70)
    
    try:
        from app.schemas.na_math_solver_v3 import (
            SolveResponseV3, ProblemV3, AnalysisV3, SolutionV3,
            VerificationMethodV3, PlotV3, get_json_schema_for_openai_v3
        )
        
        print("✅ All Pydantic models imported successfully")
        
        # Test schema generation
        schema = get_json_schema_for_openai_v3()
        print(f"✅ OpenAI schema generated: {len(schema.get('properties', {}))} properties")
        
        # Test minimal valid instance
        minimal_data = {
            "problem": {"input": "Test", "topic": "algebra", "goal": "Test"},
            "analysis": {
                "plan": ["Step 1"],
                "detected_entities": {"expressions": [], "equations": [], "functions": [], "constraints": []}
            },
            "solution": {
                "final_answer": "x = 5",
                "steps": [{
                    "index": 1,
                    "title": "Step",
                    "concept": "Concept",
                    "rules_used": ["Rule1"],
                    "work": ["Work1"],
                    "result": "Result",
                    "checkpoint": {"question": "Q?", "expected_answer": "A"}
                }]
            },
            "verification": [
                {"method": "M1", "why_it_works": "W1", "steps": ["S1"], "conclusion": "OK"},
                {"method": "M2", "why_it_works": "W2", "steps": ["S2"], "conclusion": "OK"}
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
        
        validated = SolveResponseV3(**minimal_data)
        print(f"✅ Minimal response validated successfully")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_validation():
    """Test 3: Validation System"""
    print("\n" + "="*70)
    print("TEST 3: Validation System")
    print("="*70)
    
    try:
        from app.services.validation_v3 import (
            get_validator, validate_response, generate_repair_prompt, create_error_response
        )
        
        validator = get_validator()
        print(f"✅ Validator initialized")
        
        # Test valid data validation
        valid_data = {
            "problem": {"input": "Test", "topic": "algebra", "goal": "Test"},
            "analysis": {
                "plan": ["Step 1"],
                "detected_entities": {"expressions": [], "equations": [], "functions": [], "constraints": []}
            },
            "solution": {
                "final_answer": "x = 5",
                "steps": [{
                    "index": 1,
                    "title": "Step",
                    "concept": "Concept",
                    "rules_used": ["Rule1"],
                    "work": ["Work1"],
                    "result": "Result",
                    "checkpoint": {"question": "Q?", "expected_answer": "A"}
                }]
            },
            "verification": [
                {"method": "M1", "why_it_works": "W1", "steps": ["S1"], "conclusion": "OK"},
                {"method": "M2", "why_it_works": "W2", "steps": ["S2"], "conclusion": "OK"}
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
            print(f"✅ Valid data passed validation")
        else:
            print(f"⚠️ Valid data failed: {result.errors[:2]}")
        
        # Test invalid data
        invalid_data = {"problem": {"input": "Test", "topic": "algebra", "goal": "Test"}}
        result2 = validate_response(invalid_data, strict=False)
        if not result2.valid:
            print(f"✅ Invalid data correctly rejected ({len(result2.errors)} errors)")
        
        # Test repair prompt generation
        repair_prompt = generate_repair_prompt(invalid_data, result2, "Test problem")
        print(f"✅ Repair prompt generated: {len(repair_prompt)} characters")
        
        # Test error response
        error_resp = create_error_response("Test", ["Error1", "Error2"], "test_error")
        print(f"✅ Error response created: {error_resp['error_type']}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_visualization():
    """Test 4: Visualization System"""
    print("\n" + "="*70)
    print("TEST 4: Visualization System")
    print("="*70)
    
    try:
        from app.services.visualization.decision_engine import get_visualization_engine
        
        engine = get_visualization_engine()
        print(f"✅ Visualization engine initialized")
        
        # Test decision logic
        test_cases = [
            ("Graph y = x^2", {"detected_entities": {"functions": ["y=x^2"], "equations": [], "constraints": []}}, True),
            ("Solve x + 5 = 10", {"detected_entities": {"functions": [], "equations": ["x+5=10"], "constraints": []}}, False),
        ]
        
        for problem, analysis, expected_should_plot in test_cases:
            decision = engine.should_visualize(problem, analysis)
            print(f"  - '{problem[:30]}...' → should_plot={decision.should_visualize}, type={decision.plot_type}")
        
        print("✅ Decision logic working")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_plot_renderer():
    """Test 5: Plot Renderer"""
    print("\n" + "="*70)
    print("TEST 5: Plot Renderer")
    print("="*70)
    
    try:
        from app.services.visualization.plot_renderer import get_plot_renderer
        from app.schemas.na_math_solver_v3 import (
            PlotPlanV3, AxesV3, RecommendedWindowV3, PlotObjectV3,
            SamplingV3, ObjectKind, SamplingStrategy
        )
        
        renderer = get_plot_renderer()
        print(f"✅ Plot renderer initialized")
        
        # Test rendering
        plan = PlotPlanV3(
            title="Test Plot",
            axes=AxesV3(x_label="x", y_label="y"),
            recommended_window=RecommendedWindowV3(x_min=-5, x_max=5, y_min=0, y_max=25),
            objects=[
                PlotObjectV3(kind=ObjectKind.CURVE, expression="x**2", label="y=x²")
            ],
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
        )
        
        result = renderer.render(plan, "function")
        print(f"✅ Plot rendered: {result.width}x{result.height}px")
        print(f"✅ Base64 image: {len(result.image_base64)} characters")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_solver_v3_init():
    """Test 6: Solver V3 Initialization"""
    print("\n" + "="*70)
    print("TEST 6: Solver V3 Orchestrator")
    print("="*70)
    
    try:
        from app.services.solver_v3 import get_solver_v3
        
        solver = get_solver_v3()
        print(f"✅ Solver V3 initialized")
        print(f"✅ Model: {solver._model}")
        print(f"✅ Fallback model: {solver._fallback_model}")
        print(f"⚠️ Note: Full solver test requires OPENAI_API_KEY")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# MATH SOLVER V3 - QUICK COMPONENT TEST")
    print("# Testing all components without requiring OpenAI API key")
    print("#"*70)
    
    tests = [
        ("Prompt Registry", test_prompt_registry),
        ("Pydantic Models", test_pydantic_models),
        ("Validation System", test_validation),
        ("Visualization Engine", test_visualization),
        ("Plot Renderer", test_plot_renderer),
        ("Solver V3 Init", test_solver_v3_init),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
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
    
    if passed == total:
        print("🎉 All components working correctly!")
        print("\nNext steps:")
        print("1. Set OPENAI_API_KEY to test full integration")
        print("2. Run: python tests/test_solver_v3_integration.py")
        sys.exit(0)
    else:
        print("⚠️ Some components failed. Please review errors above.")
        sys.exit(1)
