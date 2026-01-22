import sys
import os
sys.path.append(os.getcwd()) # Assumes running from backend dir

from app.services.response_mapper import map_minimal_to_canonical
from app.services.validation_v3 import validate_response
from app.schemas.na_math_solver_v3 import SolveResponseV3
import json

minimal = {
        "final_answer": "42",
        "steps": ["Step 1: Calculate", "Step 2: Done"],
        "topic": "Math",
        "confidence_score": 0.99
    }

canonical = map_minimal_to_canonical(minimal, "What is 6 * 7?")
print("Canonical Keys:", canonical.keys())

validation = validate_response(canonical, strict=True)
if not validation.valid:
    print("VALIDATION FAILED:")
    for err in validation.errors:
        print(f"- {err}")
else:
    print("VALIDATION PASSED")
