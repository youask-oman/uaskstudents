import re
from typing import Optional


_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF]")
_ALNUM_ONLY_RE = re.compile(r"[^A-Z0-9]")


def extract_pairing_code(raw_text: str, code_length: int = 8) -> Optional[str]:
    """
    Extract and normalize WhatsApp pairing code.

    Accepts variants like:
    - CODE ABCD1234
    - code abcd1234
    - CoDe a-b c_d:1 2 3 4
    - @@@ABCD-1234###
    """
    if code_length <= 0:
        return None

    text = _ZERO_WIDTH_RE.sub("", str(raw_text or "")).strip()
    if not text:
        return None
    up = text.upper()

    joined_pattern = (
        rf"([A-Z0-9](?:[\s\-\._:]*[A-Z0-9]){{{max(0, code_length - 1)}}})"
        rf"(?![\s\-\._:]*[A-Z0-9])"
    )

    prefix = re.search(r"\bCODE\b", up)
    if prefix:
        tail = up[prefix.end() :]
        full = re.fullmatch(rf"[^A-Z0-9]*{joined_pattern}[^A-Z0-9]*", tail)
        if full:
            candidate = _ALNUM_ONLY_RE.sub("", full.group(1))
            if len(candidate) == code_length:
                return candidate
        return None

    # Accept plain code-only messages with separators/symbol wrappers.
    full = re.fullmatch(rf"[^A-Z0-9]*{joined_pattern}[^A-Z0-9]*", up)
    if full:
        candidate = _ALNUM_ONLY_RE.sub("", full.group(1))
        if len(candidate) == code_length:
            return candidate

    return None
