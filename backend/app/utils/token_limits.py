from typing import Optional

def get_effective_max_tokens(mode: str, learning_mode: Optional[str]) -> int:
    """
    Returns a deterministic max_output_tokens cap based on mode and learning_mode.
    
    Caps:
      - minimal + solve: 900
      - minimal + study: 1600 (though study is usually disabled in minimal)
      - detailed + solve: 3000
      - detailed + study: 4500
      - default: 1000
    """
    normalized_mode = (mode or "minimal").lower()
    normalized_learning = (learning_mode or "solve").lower()
    
    if normalized_mode == "minimal":
        if normalized_learning == "study":
            return 1600
        return 900
    elif normalized_mode == "detailed":
        if normalized_learning == "study":
            return 12000
        return 6000
        
    return 1000
