import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from sympy import Symbol, sqrt, sympify  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency safety
    Symbol = None  # type: ignore
    sqrt = None  # type: ignore
    sympify = None  # type: ignore


logger = logging.getLogger(__name__)


_CHOICE_LINE_RE = re.compile(r"^\s*[\(\[]?([A-Ea-e])[\)\].:\-]\s*(.+?)\s*$")
_INLINE_CHOICE_RE = re.compile(
    r"(?is)(?:^|\s)[\(\[]?([A-Ea-e])[\)\].:\-]\s*(.+?)(?=(?:\s+[\(\[]?[A-Ea-e][\)\].:\-]\s+)|$)"
)
_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_MATH_TERMS_RE = re.compile(
    r"\b(solve|find|ratio|triangle|circle|function|graph|equation|angle|probability|area|perimeter|x|y)\b",
    re.IGNORECASE,
)
_DUP_NORMALIZE_WS_RE = re.compile(r"\s+")


def _normalize_preserve_lines(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned = [line.rstrip() for line in lines]
    out = "\n".join(cleaned)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _safe_lower(s: str) -> str:
    return _DUP_NORMALIZE_WS_RE.sub(" ", s.strip().lower())


def _garbage_char_rate(text: str) -> float:
    if not text:
        return 1.0
    total = len(text)
    garbage = text.count("�") + len(_CTRL_RE.findall(text))
    return garbage / float(max(total, 1))


def _has_duplication(text: str) -> bool:
    chunks = [c.strip() for c in text.split("\n") if c.strip()]
    counts: Dict[str, int] = {}
    for chunk in chunks:
        key = _safe_lower(chunk)
        if len(key) < 12:
            continue
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > 2:
            return True
    return False


def detect_mcq_choices(text: str) -> Optional[Dict[str, str]]:
    lines = text.split("\n")
    choices: Dict[str, str] = {}
    choice_line_indexes: List[int] = []
    for idx, line in enumerate(lines):
        m = _CHOICE_LINE_RE.match(line)
        if not m:
            continue
        key = m.group(1).lower()
        val = m.group(2).strip()
        if key in choices or not val:
            continue
        choices[key] = val
        choice_line_indexes.append(idx)

    if len(choices) >= 3:
        return choices

    inline_choices: Dict[str, str] = {}
    for m in _INLINE_CHOICE_RE.finditer(text):
        key = m.group(1).lower()
        val = _normalize_preserve_lines(m.group(2))
        if key in inline_choices or not val:
            continue
        inline_choices[key] = val

    if len(inline_choices) >= 3:
        return inline_choices
    return None


def _extract_stem(text: str, choices: Optional[Dict[str, str]]) -> str:
    if not choices:
        return _normalize_preserve_lines(text)
    lines = text.split("\n")
    stem_lines: List[str] = []
    for line in lines:
        if _CHOICE_LINE_RE.match(line):
            break
        stem_lines.append(line)
    if stem_lines:
        return _normalize_preserve_lines("\n".join(stem_lines))
    inline = _INLINE_CHOICE_RE.search(text)
    if inline:
        return _normalize_preserve_lines(text[: inline.start()])
    return _normalize_preserve_lines(text)


def _normalize_math_expr(raw: str) -> str:
    expr = raw.strip()
    expr = expr.replace("−", "-").replace("–", "-").replace("—", "-")
    expr = expr.replace("×", "*").replace("÷", "/")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\\sqrt\s*\{([^}]+)\}", r"sqrt(\1)", expr)
    expr = re.sub(r"√\s*\(([^)]+)\)", r"sqrt(\1)", expr)
    expr = re.sub(r"√\s*([A-Za-z0-9]+)", r"sqrt(\1)", expr)
    expr = re.sub(r"^[\(\[]?[A-Ea-e][\)\].:\-]\s*", "", expr)
    return expr.strip()


def _is_parsable_expr(expr: str) -> bool:
    if not expr:
        return False
    if sympify is None or Symbol is None or sqrt is None:
        return False
    local_dict = {
        "x": Symbol("x"),
        "y": Symbol("y"),
        "z": Symbol("z"),
        "a": Symbol("a"),
        "b": Symbol("b"),
        "c": Symbol("c"),
        "m": Symbol("m"),
        "n": Symbol("n"),
        "t": Symbol("t"),
        "sqrt": sqrt,
    }
    try:
        sympify(expr, locals=local_dict, evaluate=True)
        return True
    except Exception:
        return False


def _ratio_parse_ok(choice: str) -> bool:
    parts = [p.strip() for p in choice.split(":") if p.strip()]
    if len(parts) < 2:
        return _is_parsable_expr(_normalize_math_expr(choice))
    return all(_is_parsable_expr(_normalize_math_expr(p)) for p in parts)


def _math_signal_score(text: str) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    checks = [
        (bool(re.search(r"\d", text)), 3, "Contains digits"),
        (("°" in text) or bool(re.search(r"\bdeg\b", text, re.IGNORECASE)), 3, "Contains angle notation"),
        (bool(re.search(r"[+\-*/=:]", text)), 4, "Contains math operators"),
        (("√" in text) or ("\\sqrt" in text), 4, "Contains square-root notation"),
        (bool(_MATH_TERMS_RE.search(text)), 6, "Contains math terms"),
    ]
    for ok, pts, reason in checks:
        if ok:
            score += pts
            reasons.append(reason)
    return min(20, score), reasons


def _pick_text_source(ocr_result: Dict[str, Any]) -> Tuple[str, Optional[int], Optional[str]]:
    structured = ocr_result.get("structured_json")
    if isinstance(structured, dict):
        questions = structured.get("questions")
        if isinstance(questions, list) and questions:
            first = questions[0] if isinstance(questions[0], dict) else {}
            q_text = str(first.get("question_text") or first.get("text") or "").strip()
            page_index = first.get("page_index")
            page = page_index if isinstance(page_index, int) else None
            latex = first.get("latex")
            return _normalize_preserve_lines(q_text), page, (str(latex) if isinstance(latex, str) else None)
    extracted = str(ocr_result.get("extracted_text") or "").strip()
    return _normalize_preserve_lines(extracted), None, None


def assess_math_validity(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    attempt_id = str(ocr_result.get("ocr_attempt_id") or "unknown")
    request_id = str(ocr_result.get("request_id") or "")
    reasons: List[str] = []
    warnings: List[str] = []

    text, page_index, latex = _pick_text_source(ocr_result)
    choices = detect_mcq_choices(text)
    kind = "mcq" if choices and len(choices) >= 3 else "free_response"
    stem = _extract_stem(text, choices)

    stem_len = len(stem)
    structure_score = 0
    if stem_len >= 20:
        structure_score += 15
        reasons.append("Stem length >= 20")
    if kind == "mcq" and choices:
        if len(choices) >= 3:
            structure_score += 15
            reasons.append("Detected MCQ with >=3 choices")
        if len(choices) >= 4:
            structure_score += 10
            reasons.append("Detected MCQ with >=4 choices")

    cleanliness_score = 0
    if text:
        cleanliness_score += 10
    garbage_rate = _garbage_char_rate(text)
    if garbage_rate < 0.005:
        cleanliness_score += 10
    else:
        warnings.append(f"HIGH_GARBAGE_CHAR_RATE:{garbage_rate:.3%}")
    has_dup = _has_duplication(text)
    if not has_dup:
        cleanliness_score += 5
    else:
        warnings.append("DUPLICATION_DETECTED")

    math_signal_score, math_reasons = _math_signal_score(text)
    reasons.extend(math_reasons)

    parsability_score = 0
    parsed_count = 0
    parse_total = 0
    if kind == "mcq" and choices:
        parse_total = len(choices)
        for value in choices.values():
            if _ratio_parse_ok(value):
                parsed_count += 1
        parsability_score = int(round(15 * (parsed_count / max(parse_total, 1))))
        reasons.append(f"Parsable choices: {parsed_count}/{parse_total}")
    elif latex:
        parse_total = 1
        parsed_count = 1 if _is_parsable_expr(_normalize_math_expr(latex)) else 0
        parsability_score = int(round(15 * parsed_count))
        if parsed_count:
            reasons.append("Latex expression parsed")
        else:
            warnings.append("LATEX_NOT_PARSABLE")

    confidence_percent = int(
        max(0, min(100, structure_score + cleanliness_score + math_signal_score + parsability_score))
    )

    valid = bool(
        (stem_len >= 20 and math_signal_score >= 8)
        or ((kind == "mcq") and bool(choices) and len(choices) >= 3 and math_signal_score >= 6)
    )
    if not valid:
        warnings.append("VALIDITY_RULES_NOT_MET")
    if confidence_percent < 50:
        warnings.append("LOW_CONFIDENCE")

    failed_checks: List[str] = []
    if stem_len < 20:
        failed_checks.append("stem_length")
    if math_signal_score < 6:
        failed_checks.append("math_signal")
    if kind == "mcq" and (not choices or len(choices) < 3):
        failed_checks.append("mcq_choices")
    if garbage_rate >= 0.005:
        failed_checks.append("garbage_rate")
    if has_dup:
        failed_checks.append("duplication")

    runtime_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "math_validity_assess request_id=%s ocr_attempt_id=%s runtime_ms=%s valid=%s confidence=%s failed_checks=%s",
        request_id,
        attempt_id,
        runtime_ms,
        valid,
        confidence_percent,
        ",".join(failed_checks) or "none",
    )

    return {
        "is_valid_math_problem": valid,
        "confidence_percent": confidence_percent,
        "reasons": reasons,
        "warnings": warnings,
        "normalized_question": {
            "kind": kind,
            "stem": stem,
            "choices": choices if kind == "mcq" and choices else None,
            "page_index": page_index,
            "meta": {
                "stem_length": stem_len,
                "structure_score": structure_score,
                "cleanliness_score": cleanliness_score,
                "math_signal_score": math_signal_score,
                "parsability_score": parsability_score,
            },
        },
    }
