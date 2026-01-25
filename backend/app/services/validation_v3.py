"""
JSON Schema validation with automatic repair loop for Math Solver V3.

Validates LLM responses against the canonical JSON Schema Draft 2020-12
and attempts automatic repair if validation fails.
"""

import json
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from jsonschema import validate, ValidationError as JsonSchemaValidationError, Draft202012Validator
from pydantic import ValidationError as PydanticValidationError

from app.schemas.na_math_solver_v3 import SolveResponseV3, ErrorResponseV3, get_json_schema_for_openai_v3
from app.utils.schema_deref import deref_json_schema
from app.prompts import get_schema


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[str]
    error_details: List[Dict[str, Any]]
    pydantic_errors: Optional[List[Dict[str, Any]]] = None


class SchemaValidator:
    """
    Validates responses against JSON Schema with repair capability.
    
    Features:
    - JSON Schema Draft 2020-12 validation
    - Pydantic v2 validation
    - Detailed error reporting
    - Automatic repair suggestions
    """
    
    def __init__(self):
        """Initialize validator with source-of-truth Pydantic schema."""
        # Use simple un-dereferenced schema for local validation if validator supports refs, 
        # OR use dereferenced one. JSonschema library handles $refs if specificed correctly.
        # But to be consistent with what OpenAI sees, we use the dereferenced strictly-typed schema.
        try:
            raw_schema = get_json_schema_for_openai_v3()
            self.schema = deref_json_schema(raw_schema)
        except Exception as e:
            # Fallback (log error)
            print(f"Error loading Pydantic schema for validation: {e}. Falling back to file registry.")
            self.schema = get_schema("na_math_solver")
            
        self.validator = Draft202012Validator(self.schema)
    
    def validate(self, data: Dict[str, Any], strict: bool = True) -> ValidationResult:
        """
        Validate response data against schema.
        
        Args:
            data: Response data to validate
            strict: If True, also validate with Pydantic for extra checks
        
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        error_details = []
        pydantic_errors = None
        
        # 1. JSON Schema validation
        # 1. JSON Schema validation
        for i, error in enumerate(self.validator.iter_errors(data)):
            if i >= 20: 
                break
            
            errors.append(f"JSON Schema error: {error.message}")
            error_details.append({
                "type": "json_schema",
                "message": error.message,
                "path": list(error.absolute_path),
                "schema_path": list(error.absolute_schema_path),
                "validator": error.validator,
                "validator_value": error.validator_value
            })
        
        # 2. Pydantic validation (stricter checks)
        if strict:
            try:
                SolveResponseV3(**data)
            except PydanticValidationError as e:
                pydantic_errors = []
                for error in e.errors():
                    error_msg = f"Pydantic: {error['loc']} - {error['msg']}"
                    errors.append(error_msg)
                    pydantic_errors.append({
                        "loc": error["loc"],
                        "msg": error["msg"],
                        "type": error["type"]
                    })
            except Exception as e:
                errors.append(f"Pydantic validation error: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            error_details=error_details,
            pydantic_errors=pydantic_errors
        )
    
    def generate_repair_prompt(
        self,
        original_data: Dict[str, Any],
        validation_result: ValidationResult,
        problem_text: str
    ) -> str:
        """
        Generate a repair prompt for the LLM.
        
        Args:
            original_data: The invalid response
            validation_result: Validation errors
            problem_text: Original problem
        
        Returns:
            Repair prompt string
        """
        errors_str = "\n".join(f"  - {err}" for err in validation_result.errors[:5])  # Limit to first 5
        
        repair_prompt = f"""The previous response had validation errors that must be fixed.

**Original Problem**: {problem_text}

**Validation Errors**:
{errors_str}

**Previous Response** (invalid):
{json.dumps(original_data, indent=2)[:2000]}...

**CRITICAL INSTRUCTIONS FOR REPAIR**:
1. **Fix ALL validation errors** listed above.
2. **Schema Compliance**: You must match the v1.0 schema exactly. 
   - Ensure all top-level keys exist: problem, classification, refusal, assumptions, steps, final_answer, verification, visuals, quality.
3. **Visuals Logic**:
   - If `visuals.should_visualize` is true, you MUST provide `plots` array.
   - If `visuals.should_visualize` is false, provide `alternative_visual` (or empty object if strictly allowed, but prefer providing data).
4. **Refusal**:
   - Must be an object with `is_refusal` boolean.
   
6. **Return the complete corrected JSON** matching the schema exactly.

**OUTPUT**: Return ONLY the corrected JSON. No explanations.
"""
        
        return repair_prompt
    
    def create_error_response(
        self,
        problem_text: str,
        validation_errors: List[str],
        error_type: str = "validation_failure"
    ) -> Dict[str, Any]:
        """
        Create a controlled error response when validation fails.
        
        Args:
            problem_text: Original problem
            validation_errors: List of validation errors
            error_type: Type of error
        
        Returns:
            Error response dictionary
        """
        error_response = ErrorResponseV3(
            error=True,
            error_type=error_type,
            message="The solver encountered validation errors and could not produce a valid solution.",
            validation_errors=validation_errors[:10],  # Limit to first 10
            original_problem=problem_text
        )
        
        return error_response.model_dump()


# Singleton instance
_validator_instance: Optional[SchemaValidator] = None


def get_validator() -> SchemaValidator:
    """Get the global validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = SchemaValidator()
    return _validator_instance


# Convenience functions
def validate_response(data: Dict[str, Any], strict: bool = True) -> ValidationResult:
    """Validate a response using the global validator."""
    return get_validator().validate(data, strict=strict)


def generate_repair_prompt(
    original_data: Dict[str, Any],
    validation_result: ValidationResult,
    problem_text: str
) -> str:
    """Generate repair prompt using the global validator."""
    return get_validator().generate_repair_prompt(
        original_data,
        validation_result,
        problem_text
    )


def create_error_response(
    problem_text: str,
    validation_errors: List[str],
    error_type: str = "validation_failure"
) -> Dict[str, Any]:
    """Create error response using the global validator."""
    return get_validator().create_error_response(
        problem_text,
        validation_errors,
        error_type
    )


if __name__ == "__main__":
    # Test validation
    print("Testing Schema Validator...")
    
    validator = SchemaValidator()
    
    print("\n--- Test 1: Valid Response ---")
    valid_data = {
        "problem": {
            "input": "Solve x + 5 = 10",
            "topic": "algebra",
            "goal": "Find x"
        },
        "analysis": {
            "plan": ["Isolate x"],
            "detected_entities": {
                "expressions": [],
                "equations": ["x+5=10"],
                "functions": [],
                "constraints": []
            }
        },
        "solution": {
            "final_answer": "x = 5",
            "steps": [
                {
                    "index": 1,
                    "title": "Subtract 5",
                    "concept": "Inverse operations",
                    "rules_used": ["Subtraction property of equality"],
                    "work": ["x + 5 - 5 = 10 - 5", "x = 5"],
                    "result": "x = 5",
                    "checkpoint": {
                        "question": "What is x?",
                        "expected_answer": "5"
                    }
                }
            ]
        },
        "verification": [
            {
                "method": "Substitution",
                "why_it_works": "Verifies solution satisfies original equation",
                "steps": ["5 + 5 = 10 ✓"],
                "conclusion": "Correct"
            },
            {
                "method": "Inverse check",
                "why_it_works": "Confirms result via inverse operation",
                "steps": ["10 - 5 = 5 ✓"],
                "conclusion": "Confirmed"
            }
        ],
        "plot": {
            "should_plot": False,
            "plot_type": "number_line",
            "plan": {
                "title": "Solution point",
                "axes": {"x_label": "x", "y_label": ""},
                "recommended_window": {"x_min": 0, "x_max": 10, "y_min": -1, "y_max": 1},
                "objects": [{"kind": "points", "expression": "x=5", "label": "Solution"}],
                "annotations": [],
                "sampling": {"strategy": "uniform", "resolution": 100}
            }
        },
        "similar_examples": [
            {"problem": "x + 3 = 8", "key_idea": "Inverse ops", "short_solution": "x = 5"},
            {"problem": "x - 2 = 7", "key_idea": "Inverse ops", "short_solution": "x = 9"}
        ],
        "meta": {
            "confidence": 0.95,
            "localization": {"region": "north_america", "notation": "standard"},
            "rounding_policy": "2 decimal places"
        }
    }
    
    result = validator.validate(valid_data, strict=True)
    if result.valid:
        print("✅ Valid response passed validation")
    else:
        print(f"❌ Validation failed: {result.errors}")
    
    print("\n--- Test 2: Invalid Response (Missing Required Fields) ---")
    invalid_data = {
        "problem": {"input": "Test", "topic": "algebra", "goal": "Solve"},
        # Missing many required fields
    }
    
    result = validator.validate(invalid_data, strict=False)
    if not result.valid:
        print(f"✅ Correctly caught {len(result.errors)} validation errors")
        print(f"   First error: {result.errors[0][:100]}...")
    else:
        print("❌ Should have failed validation")
    
    print("\n--- Test 3: Repair Prompt Generation ---")
    repair_prompt = validator.generate_repair_prompt(invalid_data, result, "Solve x + 5 = 10")
    print(f"✅ Generated repair prompt: {len(repair_prompt)} characters")
    print(f"   Starts with: {repair_prompt[:100]}...")
    
    print("\n--- Test 4: Error Response Creation ---")
    error_resp = validator.create_error_response(
        "Solve x^2 = 4",
        ["Missing verification", "Invalid schema"],
        "schema_mismatch"
    )
    print(f"✅ Created error response: {error_resp['error_type']}")
    print(f"   Message: {error_resp['message'][:80]}...")
