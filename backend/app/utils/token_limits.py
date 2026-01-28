from typing import Optional

from app.services.token_policy import TokenPolicy


def get_effective_max_tokens(mode: str, learning_mode: Optional[str], policy: TokenPolicy) -> int:
    normalized_mode = (mode or "minimal").lower()
    normalized_learning = (learning_mode or "solve").lower()
    
    print(f"[LIMITS_DEBUG] Mode: {mode} -> {normalized_mode}, Learning: {learning_mode} -> {normalized_learning}")
    
    res = policy.text_output_minimal_solve
    if normalized_mode in ("minimal", "concise"):
        if normalized_learning == "study":
            res = policy.text_output_minimal_study
        else:
            res = policy.text_output_minimal_solve
    elif normalized_mode in ("detailed", "tutor"):
        if normalized_learning == "study":
            res = policy.text_output_detailed_study
        else:
            res = policy.text_output_detailed_solve
    
    print(f"[LIMITS_DEBUG] Returning {res} for mode={normalized_mode}, learning={normalized_learning}")
    return res

def get_effective_max_steps(mode: str, learning_mode: Optional[str], policy: TokenPolicy) -> int:
    normalized_mode = (mode or "minimal").lower()
    normalized_learning = (learning_mode or "solve").lower()
    
    res = policy.text_steps_minimal_solve
    if normalized_mode in ("minimal", "concise"):
        if normalized_learning == "study":
            res = policy.text_steps_minimal_study
        else:
            res = policy.text_steps_minimal_solve
    elif normalized_mode in ("detailed", "tutor"):
        if normalized_learning == "study":
            res = policy.text_steps_detailed_study
        else:
            res = policy.text_steps_detailed_solve

    print(f"[LIMITS_DEBUG] Returning {res} steps for mode={normalized_mode}, learning={normalized_learning}")
    return res
