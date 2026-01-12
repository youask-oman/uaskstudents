"""
Comprehensive test suite for Solver V2 Phases 1-4.

Tests:
- Schema validation (Pydantic models)
- JSON schema generation
- Solver service initialization
- Validation logic
- Error handling
"""

import sys
import json
import traceback
from typing import Dict, Any


def test_schema_imports():
    """Test 1: Can we import the schema modules?"""
    print("\n" + "="*70)
    print("TEST 1: Schema Imports")
    print("="*70)
    try:
        from app.schemas.solve_v2 import (
            SolveResponseV2,
            ProblemDefinitionV2,
            SolutionV2,
            VerificationV2,
            ConceptV2,
            VisualRequestV2,
            VisualPolicyV2,
            get_json_schema_for_openai
        )
        print("✅ All schema imports successful")
        return True
    except Exception as e:
        print(f"❌ Schema import failed: {e}")
        traceback.print_exc()
        return False


def test_schema_validation():
    """Test 2: Validate a complete valid response."""
    print("\n" + "="*70)
    print("TEST 2: Schema Validation (Valid Response)")
    print("="*70)
    
    try:
        from app.schemas.solve_v2 import SolveResponseV2
        
        # Valid response matching schema
        valid_response = {
            "problem": {
                "goal": "Solve for x",
                "latex": "2x+7=19",
                "givens": ["Equation: 2x+7=19"],
                "unknowns": ["x"],
                "assumptions": ["x is a real number"]
            },
            "solution": {
                "plan": ["Isolate x using inverse operations"],
                "steps": [
                    {
                        "index": 1,
                        "title": "Subtract 7",
                        "explanation": "We subtract 7 from both sides to isolate the term with x.",
                        "why": "Subtraction is the inverse of addition, maintaining equation balance.",
                        "math": {"latex_lines": ["2x+7-7=19-7", "2x=12"]},
                        "common_mistake": "Forgetting to subtract from both sides",
                        "checkpoint": "Does 2x=12 look correct?",
                        "visual_refs": []
                    },
                    {
                        "index": 2,
                        "title": "Divide by 2",
                        "explanation": "We divide both sides by 2 to get x alone.",
                        "why": "Division is the inverse of multiplication.",
                        "math": {"latex_lines": ["x=6"]},
                        "common_mistake": "Dividing only one side",
                        "checkpoint": "Is x=6 the solution?",
                        "visual_refs": []
                    }
                ],
                "final_answer": "x = 6"
            },
            "verification": {
                "methods_used": [
                    {
                        "name": "Substitution",
                        "description": "Substitute x=6 back into original equation",
                        "steps": ["2(6)+7 = 12+7 = 19 ✓"],
                        "expected_result": "19 = 19"
                    }
                ]
            },
            "concepts": [
                {
                    "name": "Linear Equations",
                    "description": "Equations with variable to the first power",
                    "applies_here": "This problem is a linear equation in one variable"
                },
                {
                    "name": "Inverse Operations",
                    "description": "Operations that undo each other",
                    "applies_here": "We use subtraction and division as inverses"
                },
                {
                    "name": "Equation Balance",
                    "description": "Both sides must remain equal",
                    "applies_here": "We perform same operation on both sides"
                }
            ],
            "visual_policy": {
                "required": False,
                "reason": "Simple algebraic manipulation doesn't require visualization"
            },
            "visuals_suggested": [],
            "visuals": [],
            "response_intent": ["step_by_step"],
            "difficulty": "trivial",
            "confidence": 0.95
        }
        
        validated = SolveResponseV2(**valid_response)
        print("✅ Valid response passed Pydantic validation")
        print(f"   - Difficulty: {validated.difficulty}")
        print(f"   - Steps: {len(validated.solution.steps)}")
        print(f"   - Concepts: {len(validated.concepts)}")
        print(f"   - Verification methods: {len(validated.verification.methods_used)}")
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        traceback.print_exc()
        return False


def test_schema_validation_errors():
    """Test 3: Test validation catches errors."""
    print("\n" + "="*70)
    print("TEST 3: Schema Validation (Error Catching)")
    print("="*70)
    
    try:
        from app.schemas.solve_v2 import SolveResponseV2
        
        # Missing required fields
        invalid_response = {
            "problem": {"goal": "Test"},
            "solution": {"plan": [], "steps": [], "final_answer": ""},
            # Missing verification, concepts, visual_policy, difficulty, confidence
        }
        
        try:
            validated = SolveResponseV2(**invalid_response)
            print("❌ Should have failed validation but didn't")
            return False
        except Exception as e:
            print(f"✅ Correctly caught validation error: {str(e)[:100]}...")
            return True
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        traceback.print_exc()
        return False


def test_json_schema_generation():
    """Test 4: JSON schema generation for OpenAI."""
    print("\n" + "="*70)
    print("TEST 4: JSON Schema Generation")
    print("="*70)
    
    try:
        from app.schemas.solve_v2 import get_json_schema_for_openai
        
        schema = get_json_schema_for_openai()
        
        # Check schema structure
        assert schema["type"] == "object", "Schema type should be object"
        assert "properties" in schema, "Schema should have properties"
        assert "required" in schema, "Schema should have required fields"
        assert schema.get("additionalProperties") == False, "Should not allow additional properties"
        
        # Check required fields
        required = schema["required"]
        expected_required = ["problem", "solution", "verification", "concepts", "visual_policy", "difficulty", "confidence"]
        for field in expected_required:
            assert field in required, f"Required field '{field}' missing"
        
        print("✅ JSON schema generated successfully")
        print(f"   - Type: {schema['type']}")
        print(f"   - Required fields: {len(required)}")
        print(f"   - Properties: {len(schema['properties'])}")
        return True
        
    except Exception as e:
        print(f"❌ JSON schema generation failed: {e}")
        traceback.print_exc()
        return False


def test_solver_imports():
    """Test 5: Solver service imports."""
    print("\n" + "="*70)
    print("TEST 5: Solver Service Imports")
    print("="*70)
    
    try:
        from app.services.solver_v2 import SolverServiceV2, solver_service_v2
        print("✅ Solver service imports successful")
        print(f"   - Singleton instance available: {solver_service_v2 is not None}")
        return True
    except Exception as e:
        print(f"❌ Solver import failed: {e}")
        traceback.print_exc()
        return False


def test_solver_initialization():
    """Test 6: Solver service initialization."""
    print("\n" + "="*70)
    print("TEST 6: Solver Service Initialization")
    print("="*70)
    
    try:
        from app.services.solver_v2 import SolverServiceV2
        
        solver = SolverServiceV2()
        
        # Check attributes
        assert hasattr(solver, '_client'), "Solver should have _client attribute"
        assert hasattr(solver, '_default_model'), "Solver should have _default_model"
        assert hasattr(solver, '_fallback_model'), "Solver should have _fallback_model"
        
        # Check methods
        assert hasattr(solver, 'solve_problem_v2'), "Should have solve_problem_v2 method"
        assert hasattr(solver, '_validate_response'), "Should have _validate_response method"
        assert hasattr(solver, '_generate_chat_content'), "Should have _generate_chat_content method"
        
        print("✅ Solver initialized successfully")
        print(f"   - Default model: {solver._default_model}")
        print(f"   - Fallback model: {solver._fallback_model}")
        return True
        
    except Exception as e:
        print(f"❌ Solver initialization failed: {e}")
        traceback.print_exc()
        return False


def test_validation_imports():
    """Test 7: Validation module imports."""
    print("\n" + "="*70)
    print("TEST 7: Validation Module Imports")
    print("="*70)
    
    try:
        from app.services.validation import (
            validate_solve_response,
            enforce_visual_policy,
            check_minimum_requirements,
            ValidationError
        )
        print("✅ Validation module imports successful")
        return True
    except Exception as e:
        print(f"❌ Validation import failed: {e}")
        traceback.print_exc()
        return False


def test_validation_logic():
    """Test 8: Validation logic."""
    print("\n" + "="*70)
    print("TEST 8: Validation Logic")
    print("="*70)
    
    try:
        from app.services.validation import validate_solve_response
        
        # Valid response (same as Test 2)
        valid_response = {
            "problem": {
                "goal": "Solve for x",
                "latex": "2x+7=19",
                "givens": ["Equation: 2x+7=19"],
                "unknowns": ["x"],
                "assumptions": []
            },
            "solution": {
                "plan": ["Isolate x"],
                "steps": [
                    {
                        "index": 1,
                        "title": "Step 1",
                        "explanation": "We subtract 7 from both sides.",
                        "why": "Inverse operation",
                        "math": {"latex_lines": ["2x=12"]},
                        "common_mistake": "Not subtracting from both sides",
                        "checkpoint": "Check",
                        "visual_refs": []
                    },
                    {
                        "index": 2,
                        "title": "Step 2",
                        "explanation": "We divide both sides by 2.",
                        "why": "Inverse operation",
                        "math": {"latex_lines": ["x=6"]},
                        "common_mistake": "Not dividing both sides",
                        "checkpoint": "Check",
                        "visual_refs": []
                    }
                ],
                "final_answer": "x = 6"
            },
            "verification": {
                "methods_used": [{
                    "name": "Substitution",
                    "description": "Test",
                    "steps": ["2(6)+7=19"],
                    "expected_result": "19=19"
                }]
            },
            "concepts": [
                {"name": "C1", "description": "D1", "applies_here": "Application here 1"},
                {"name": "C2", "description": "D2", "applies_here": "Application here 2"},
                {"name": "C3", "description": "D3", "applies_here": "Application here 3"}
            ],
            "visual_policy": {"required": False, "reason": "Simple problem"},
            "visuals_suggested": [],
            "visuals": [],
            "response_intent": ["step_by_step"],
            "difficulty": "trivial",
            "confidence": 0.9
        }
        
        result = validate_solve_response(valid_response, "2x+7=19", strict=False)
        
        if result["valid"]:
            print("✅ Validation logic works correctly")
            print(f"   - Errors: {result['errors']}")
            return True
        else:
            print(f"❌ Valid response failed validation: {result['errors']}")
            return False
            
    except Exception as e:
        print(f"❌ Validation logic test failed: {e}")
        traceback.print_exc()
        return False


def test_chat_content_generation():
    """Test 9: Chat content generation."""
    print("\n" + "="*70)
    print("TEST 9: Chat Content Generation")
    print("="*70)
    
    try:
        from app.services.solver_v2 import SolverServiceV2
        
        solver = SolverServiceV2()
        
        response_data = {
            "solution": {
                "plan": ["Step 1", "Step 2"],
                "steps": [
                    {
                        "index": 1,
                        "title": "Isolate term",
                        "explanation": "We subtract 7 from both sides to move constant.",
                        "math": {"latex_lines": ["2x=12"]}
                    },
                    {
                        "index": 2,
                        "title": "Solve for x",
                        "explanation": "We divide both sides by 2.",
                        "math": {"latex_lines": ["x=6"]}
                    }
                ],
                "final_answer": "x = 6"
            },
            "verification": {
                "methods_used": [{
                    "name": "Substitution",
                    "steps": ["2(6)+7 = 19 ✓"]
                }]
            }
        }
        
        content = solver._generate_chat_content(response_data)
        
        assert "## Plan" in content, "Content should have Plan section"
        assert "## Steps" in content, "Content should have Steps section"
        assert "## Answer" in content, "Content should have Answer section"
        assert "## Verification" in content, "Content should have Verification section"
        assert "x = 6" in content, "Content should include final answer"
        
        print("✅ Chat content generated successfully")
        print(f"   - Content length: {len(content)} characters")
        print(f"   - Sections: Plan, Steps, Answer, Verification")
        return True
        
    except Exception as e:
        print(f"❌ Chat content generation failed: {e}")
        traceback.print_exc()
        return False


def test_error_response():
    """Test 10: Error response creation."""
    print("\n" + "="*70)
    print("TEST 10: Error Response Creation")
    print("="*70)
    
    try:
        from app.services.solver_v2 import SolverServiceV2
        
        solver = SolverServiceV2()
        error_response = solver._create_error_response("Test error message")
        
        assert error_response["difficulty"] == "trivial", "Error response should have difficulty"
        assert error_response["confidence"] == 0.0, "Error response should have 0 confidence"
        assert "error" in error_response["_model"], "Model should indicate error"
        assert len(error_response["concepts"]) >= 3, "Should have minimum concepts"
        
        print("✅ Error response created successfully")
        print(f"   - Contains: {error_response['_content'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error response creation failed: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "#"*70)
    print("# SOLVER V2 - PHASES 1-4 COMPREHENSIVE TEST SUITE")
    print("#"*70)
    
    tests = [
        ("Schema Imports", test_schema_imports),
        ("Schema Validation (Valid)", test_schema_validation),
        ("Schema Validation (Errors)", test_schema_validation_errors),
        ("JSON Schema Generation", test_json_schema_generation),
        ("Solver Imports", test_solver_imports),
        ("Solver Initialization", test_solver_initialization),
        ("Validation Imports", test_validation_imports),
        ("Validation Logic", test_validation_logic),
        ("Chat Content Generation", test_chat_content_generation),
        ("Error Response", test_error_response),
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
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
