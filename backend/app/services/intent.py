import re

def should_require_visual(user_query: str) -> tuple[bool, str | None]:
    """
    Analyzes user text to determine if a visual graph/plot should be strictly required.
    Returns (required: bool, reason: str)
    """
    q = user_query.lower().strip()
    
    # 1. Explicit requested keywords (Case-insensitive)
    keywords = ["graph", "plot", "draw", "sketch"]
    if any(k in q for k in keywords):
        return True, "User explicitly requested a visual."
        
    # 2. Required even if not said (Line passing through points)
    # Exact patterns requested by user
    if "equation of the line" in q:
        if "passing through the points" in q or "through" in q:
            return True, "Standard problem type (line through points) requires mandatory visualization."
            
    # Pattern for coordinates like (x,y)
    if "line" in q and re.search(r'\(-?\d+,\s*-?\d+\)', q):
        return True, "Detected coordinate points for a line problem; visual required."
        
    return False, None
