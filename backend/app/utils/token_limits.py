from typing import Optional

from app.services.token_policy import TokenPolicy


def get_effective_max_tokens(mode: str, learning_mode: Optional[str], policy: TokenPolicy) -> int:
    normalized_mode = (mode or "minimal").lower()
    normalized_learning = (learning_mode or "solve").lower()
    
    print(f"[LIMITS_DEBUG] Mode: {mode} -> {normalized_mode}, Learning: {learning_mode} -> {normalized_learning}")
    print(f"[LIMITS_DEBUG] Policy Detailed Solve: {policy.text_output_detailed_solve}")

    if normalized_mode == "minimal":
        if normalized_learning == "study":
            return policy.text_output_minimal_study
        return policy.text_output_minimal_solve
    if normalized_mode == "detailed":
        if normalized_learning == "study":
             print(f"[LIMITS_DEBUG] Returning Detailed Study: {policy.text_output_detailed_study}")
             return policy.text_output_detailed_study
        print(f"[LIMITS_DEBUG] Returning Detailed Solve: {policy.text_output_detailed_solve}")
        return policy.text_output_detailed_solve

    return policy.text_output_minimal_solve
