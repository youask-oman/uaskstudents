from typing import Optional

from app.services.token_policy import TokenPolicy


def get_effective_max_tokens(mode: str, learning_mode: Optional[str], policy: TokenPolicy) -> int:
    normalized_mode = (mode.lower() if mode else "minimal")
    normalized_learning = (learning_mode.lower() if learning_mode else "solve")
    
    print(f"[LIMITS_DEBUG] INPUTS: mode='{mode}', learning='{learning_mode}'")
    print(f"[LIMITS_DEBUG] NORMALIZED: mode='{normalized_mode}', learning='{normalized_learning}'")
    
    res = policy.text_output_minimal_solve
    if normalized_mode in ("minimal", "concise"):
        print("[LIMITS_DEBUG] Branch: minimal/concise")
        if normalized_learning == "study":
            res = policy.text_output_minimal_study
        else:
            res = policy.text_output_minimal_solve
    elif normalized_mode in ("detailed", "tutor"):
        print("[LIMITS_DEBUG] Branch: detailed/tutor")
        if normalized_learning == "study":
            res = policy.text_output_detailed_study
        else:
            res = policy.text_output_detailed_solve
    else:
        print(f"[LIMITS_DEBUG] Branch: ELSE (Fallthrough) - Unknown mode '{normalized_mode}'")
    
    print(f"[LIMITS_DEBUG] Returning {res}")
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
