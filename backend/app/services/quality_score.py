from __future__ import annotations

import re
from typing import List, Tuple


def _latex_balance_penalty(text: str) -> float:
    penalties = 0.0
    if text.count("{") != text.count("}"):
        penalties += 0.15
    if text.count("$") % 2 != 0:
        penalties += 0.15
    return penalties


def _garbage_penalty(text: str) -> float:
    if not text:
        return 0.6
    weird = len(re.findall(r"[\uFFFD]", text))
    ratio = weird / max(1, len(text))
    if ratio > 0.02:
        return min(0.25, ratio * 4.0)
    return 0.0


def _math_signal_penalty(text: str) -> float:
    if not text:
        return 0.25
    has_digits = bool(re.search(r"\d", text))
    has_ops = bool(re.search(r"[=+\-*/^<>]", text))
    has_vars = bool(re.search(r"\b[xynabct]\b", text, flags=re.IGNORECASE))
    if has_digits and (has_ops or has_vars):
        return 0.0
    return 0.2


def _empty_penalty(text: str) -> float:
    if not text.strip():
        return 0.8
    if len(text.strip()) < 20:
        return 0.25
    return 0.0


def compute_quality_score(question_text: str, markdown: str) -> Tuple[float, List[str]]:
    penalties = 0.0
    warnings: List[str] = []

    penalties += _empty_penalty(question_text)
    penalties += _garbage_penalty(markdown)
    penalties += _latex_balance_penalty(markdown)
    penalties += _math_signal_penalty(question_text)

    score = max(0.0, min(1.0, 1.0 - penalties))
    if score < 0.55:
        warnings.append("LOW_QUALITY_OCR")

    return score, warnings
