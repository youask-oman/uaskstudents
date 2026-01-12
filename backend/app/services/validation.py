"""
Validation utilities for Solver V2 responses.

Provides schema validation, business rule enforcement, and visual policy checking.
"""

from typing import Dict, Any, List
from app.schemas.solve_v2 import SolveResponseV2


class ValidationError(Exception):
    """Custom exception for validation failures."""
    pass


def validate_solve_response(
    response_data: Dict[str, Any],
    problem_text: str,
    strict: bool = True
) -> Dict[str, Any]:
    """
    Validate solver response against schema and business rules.
    
    Args:
        response_data: Raw response dictionary
        problem_text: Original problem text (for visual policy check)
        strict: If True, raise ValidationError on failure. If False, return errors list.
        
    Returns:
        {"valid": bool, "errors": List[str], "validated": SolveResponseV2 | None}
    """
    errors = []
    validated = None
    
    # 1. Schema validation via Pydantic
    try:
        validated = SolveResponseV2(**response_data)
    except Exception as e:
        errors.append(f"Schema validation failed: {str(e)}")
        if strict:
            raise ValidationError(f"Schema validation failed: {str(e)}")
        return {"valid": False, "errors": errors, "validated": None}
    
    # 2. Visual policy enforcement
    visual_errors = enforce_visual_policy(validated, problem_text)
    if visual_errors:
        errors.extend(visual_errors)
    
    # 3. Pydantic validators enforce business rules automatically
    # If we got here, difficulty-based rules passed
    
    is_valid = len(errors) == 0
    
    if not is_valid and strict:
        raise ValidationError(f"Validation failed: {errors}")
    
    return {
        "valid": is_valid,
        "errors": errors,
        "validated": validated
    }


def enforce_visual_policy(
    response: SolveResponseV2,
    problem_text: str
) -> List[str]:
    """
    Deterministic guard to ensure visual policy is respected.
    
    Returns list of errors (empty if valid).
    """
    errors = []
    
    # Check for visual keywords
    text_lower = problem_text.lower()
    visual_keywords = ['graph', 'plot', 'draw', 'sketch']
    has_visual_keyword = any(kw in text_lower for kw in visual_keywords)
    
    # Check problem type
    is_line_through_points = 'line' in text_lower and 'point' in text_lower
    is_system = problem_text.count('=') >= 2 and ('y=' in problem_text or 'x=' in problem_text)
    is_inequality = any(op in problem_text for op in ['>', '<', '≥', '≤', '>=', '<='])
    
    # Determine if visuals are truly required
    visual_required = (
        has_visual_keyword or 
        is_line_through_points or 
        is_system
    )
    
    # Check policy matches requirement
    if visual_required:
        if not response.visual_policy.required:
            errors.append(
                f"Visual policy should be required=True for this problem type"
            )
        if not response.visuals:
            errors.append(
                f"Visuals array is empty but visual_policy.required=True"
            )
    
    # For inequalities, suggest number_line
    if is_inequality and not response.visuals and not response.visuals_suggested:
        errors.append(
            f"Inequality problem should include number_line visual (suggested or required)"
        )
    
    return errors


def check_minimum_requirements(
    response: SolveResponseV2
) -> List[str]:
    """
    Explicit check of minimum requirements beyond Pydantic validation.
    
    This is redundant with Pydantic validators but useful for debugging.
    """
    errors = []
    
    difficulty = response.difficulty
    
    # Plan bullets
    plan_count = len(response.solution.plan)
    if difficulty == "trivial" and not (1 <= plan_count <= 2):
        errors.append(f"Trivial: expected 1-2 plan bullets, got {plan_count}")
    elif difficulty in ["standard", "advanced"] and not (2 <= plan_count <= 3):
        errors.append(f"{difficulty}: expected 2-3 plan bullets, got {plan_count}")
    
    # Steps count
    steps_count = len(response.solution.steps)
    if difficulty == "trivial" and not (2 <= steps_count <= 4):
        errors.append(f"Trivial: expected 2-4 steps, got {steps_count}")
    elif difficulty == "standard" and not (4 <= steps_count <= 10):
        errors.append(f"Standard: expected 4-10 steps, got {steps_count}")
    elif difficulty == "advanced" and not (7 <= steps_count <= 14):
        errors.append(f"Advanced: expected 7-14 steps, got {steps_count}")
    
    # Concepts count
    concepts_count = len(response.concepts)
    if not (3 <= concepts_count <= 5):
        errors.append(f"Expected 3-5 concepts, got {concepts_count}")
    
    # Verification methods
    verif_count = len(response.verification.methods_used)
    if difficulty == "trivial" and verif_count < 1:
        errors.append(f"Trivial: expected ≥1 verification method, got {verif_count}")
    elif difficulty in ["standard", "advanced"] and verif_count < 2:
        errors.append(f"{difficulty}: expected ≥2 verification methods, got {verif_count}")
    
    return errors
