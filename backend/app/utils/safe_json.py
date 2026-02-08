"""
safe_json.py (patched)
- Better multi-object handling for streamed responses that may contain extra JSON objects or junk.
- Can select the LAST complete JSON object, or the first object that contains required keys.
- Still refuses to "invent" missing braces: truncated output must be fixed upstream (timeouts / max tokens).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _iter_balanced_json_objects(s: str) -> Iterable[Tuple[str, int, int]]:
    """
    Yield (candidate_json_str, start_idx, end_idx) for each top-level balanced {...} object found in s.

    Notes:
    - Tracks quoted strings and escapes, so braces inside JSON strings do not affect depth.
    - If the last object is truncated, we *do not* raise here; the caller decides what to do.
    """
    i = 0
    n = len(s)

    while True:
        start = s.find("{", i)
        if start == -1:
            return

        depth = 0
        in_str = False
        esc = False
        end = -1

        j = start
        while j < n:
            ch = s[j]

            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break

            j += 1

        if end != -1:
            yield (s[start:end], start, end)
            i = end
            continue

        # No closing brace found for this object. Move i so we can keep searching for later objects
        # (if any). Caller can still accept earlier valid objects.
        i = start + 1


def extract_and_parse_json(
    raw: str,
    *,
    prefer_last: bool = True,
    required_keys: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Extract and parse a JSON object embedded in raw text.

    Strategy:
    1) Find balanced {...} JSON objects.
    2) Parse each candidate with json.loads.
    3) If required_keys is provided, keep only objects containing all those keys.
    4) If prefer_last=True, return the last matching object; else return first matching object.

    Raises:
      ValueError if no valid object is found.
    """
    if raw is None:
        raise ValueError("No content to parse (raw is None).")

    s = raw.strip()
    if not s:
        raise ValueError("No content to parse (empty string).")

    matches: List[Dict[str, Any]] = []
    last_truncation_hint: Optional[str] = None

    for candidate, start, end in _iter_balanced_json_objects(s):
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as e:
            # Candidate was balanced by braces but still invalid JSON.
            # Skip it; later objects might be valid.
            continue

        if required_keys:
            if not all(k in obj for k in required_keys):
                continue

        matches.append(obj)
        if not prefer_last:
            return obj

    if matches:
        return matches[-1]

    # If we got here, we found no parseable object.
    # Provide a helpful hint if the raw string *looks* like it starts a JSON object.
    # This catches the common "Truncated JSON (brace depth ...)" situation.
    first_brace = s.find("{")
    if first_brace != -1:
        # Quick brace-depth heuristic (string-aware)
        depth = 0
        in_str = False
        esc = False
        for ch in s[first_brace:]:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
        if depth > 0:
            tail = s[-200:]
            raise ValueError(
                f"Truncated JSON (brace depth {depth} at end). "
                f"Upstream stream likely ended early (timeout/max_tokens/disconnect). Tail: {repr(tail)}"
            )

    raise ValueError("No valid JSON object found in output.")


def safe_parse_json(
    output: str,
    repair_fn=None,
    *,
    prefer_last: bool = True,
    required_keys: Optional[Sequence[str]] = None,
):
    """
    Parse JSON safely. If parsing fails and repair_fn is provided, attempt repair once.

    repair_fn signature: repair_fn(bad_output: str) -> str (returns model output containing JSON)
    """
    try:
        return extract_and_parse_json(output, prefer_last=prefer_last, required_keys=required_keys)
    except Exception as e:
        if repair_fn is None:
            raise

        repaired = repair_fn(output)
        # Try parsing repaired output as well.
        return extract_and_parse_json(repaired, prefer_last=prefer_last, required_keys=required_keys)
