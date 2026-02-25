from __future__ import annotations

import re
from typing import Any, Dict


_MCQ_LINE_RE = re.compile(r"(?mi)^\s*[\(\[]?([A-Za-z])[\)\].:]\s+.+$")
_MCQ_INLINE_RE = re.compile(r"(?i)(?:^|[\s;])[\(\[]?([A-Za-z])[\)\].:]\s+")
_UNITS_RE = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(ft|cm|mm|m|in|inch|inches)\b")
_TABLE_HINT_RE = re.compile(r"(?im)(\btable\b|^\s*\|.+\|\s*$|,{2,}|\t{2,})")
_GRAPH_PRIMARY_RE = re.compile(
    r"(?i)(\bgraph\b|\bgraphed\b|\bxy-plane\b|\baxis\b|\bx-axis\b|\by-axis\b|\blegend\b|\bintercept\b|\basymptote\b|\bcurve\b|\bplot\b)"
)
_GRAPH_AXIS_TICK_RE = re.compile(r"(?is)\bx\s*[- ]?axis\b.*\by\s*[- ]?axis\b|\bticks?\b")
_GEOM_HINT_RE = re.compile(r"(?i)(radius|diameter|height|cone|cylinder|triangle|circle|diagram|silo)")
_EQUATION_TOKEN_RE = re.compile(r"[=+\-*/^]|\\frac|\\sqrt|\$|[a-zA-Z]\(")
_MCQ_VALID_LABELS = set("ABCDEFGHJKLMNPQRSTUVWXYZ")


def _extract_choice_labels(text: str) -> set[str]:
    labels: set[str] = set()
    for m in _MCQ_LINE_RE.finditer(text):
        label = m.group(1).upper()
        if label in _MCQ_VALID_LABELS:
            labels.add(label)
    if len(labels) >= 3:
        return labels
    for m in _MCQ_INLINE_RE.finditer(text):
        label = m.group(1).upper()
        if label in _MCQ_VALID_LABELS:
            labels.add(label)
    return labels


def detect_content_types(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    choices = _extract_choice_labels(text)
    has_mcq = len(choices) >= 3
    has_table = bool(_TABLE_HINT_RE.search(text))
    equation_like_lines = sum(
        1
        for line in lines
        if "=" in line and bool(re.search(r"(?i)\b[xy]\b", line))
    )
    has_graph = bool(
        _GRAPH_PRIMARY_RE.search(text)
        or _GRAPH_AXIS_TICK_RE.search(text)
        or (equation_like_lines >= 2 and bool(re.search(r"(?i)\b(x|y)\b", text)))
    )
    units_detected = bool(_UNITS_RE.search(text))
    geom_hint = bool(_GEOM_HINT_RE.search(text))
    has_geometry = bool(geom_hint or units_detected and re.search(r"(?i)(diagram|figure|height|radius|diameter)", text))

    prose_chars = len(re.sub(r"[^A-Za-z ]", "", text))
    eq_tokens = len(_EQUATION_TOKEN_RE.findall(text))
    has_equation_only = bool(eq_tokens >= 4 and prose_chars < 120 and len(lines) <= 6)

    return {
        "has_mcq": has_mcq,
        "has_table": has_table,
        "has_graph": has_graph,
        "has_geometry": has_geometry,
        "has_equation_only": has_equation_only,
        "units_detected": units_detected,
        "choice_labels_found": sorted(choices),
    }
