import re
from math import ceil


_MATH_HEAVY_PATTERN = re.compile(r"[=<>+\-*/^]|\\(frac|sqrt|int|sum|lim|log|sin|cos|tan)")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    normalized = text.strip()
    if not normalized:
        return 0
    chars_per_token = 2.5 if _MATH_HEAVY_PATTERN.search(normalized) else 4.0
    return max(1, int(ceil(len(normalized) / chars_per_token)))
