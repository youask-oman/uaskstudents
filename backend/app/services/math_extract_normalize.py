from __future__ import annotations

import re
from typing import Dict, List


_SAFE_SYMBOL_REPLACEMENTS = {
    "\u00D7": r"\\times",
    "\u00F7": r"\\div",
    "\u2264": r"\\leq",
    "\u2265": r"\\geq",
    "\u2260": r"\\neq",
    "\u2248": r"\\approx",
    "\u03C0": r"\\pi",
    "\u221A": r"\\sqrt{}",
}


def _normalize_linebreaks(text: str) -> str:
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _normalize_bullets(text: str) -> str:
    s = text
    s = s.replace("\u2022", "- ")
    s = s.replace("\u00B7", "- ")
    s = re.sub(r"^\s*[\-\*]\s*", "- ", s, flags=re.MULTILINE)
    return s


def _normalize_unicode_math(text: str) -> str:
    s = text
    for symbol, latex in _SAFE_SYMBOL_REPLACEMENTS.items():
        s = s.replace(symbol, latex)
    return s


def _repair_numeric_ocr_confusions(text: str) -> str:
    s = text
    s = re.sub(r"(?<=\d)\s*[oO]\s*(?=\d)", "0", s)
    s = re.sub(r"(?<=\d)\s*[lI]\s*(?=\d)", "1", s)
    return s


def extract_latex_blocks(text: str) -> List[str]:
    src = text or ""
    blocks: List[str] = []
    blocks.extend(re.findall(r"\$\$(.+?)\$\$", src, flags=re.DOTALL))
    blocks.extend(re.findall(r"\\\\\[(.+?)\\\\\]", src, flags=re.DOTALL))
    blocks.extend(re.findall(r"\\\\\((.+?)\\\\\)", src, flags=re.DOTALL))
    blocks.extend(re.findall(r"\$(.+?)\$", src, flags=re.DOTALL))
    cleaned = [b.strip() for b in blocks if b and b.strip()]
    seen = set()
    unique: List[str] = []
    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def normalize_math_extraction(markdown: str, json_payload: Dict[str, object]) -> Dict[str, object]:
    md = _normalize_linebreaks(markdown or "")
    md = _normalize_bullets(md)
    md = _normalize_unicode_math(md)
    md = _repair_numeric_ocr_confusions(md)

    latex_blocks = extract_latex_blocks(md)
    question_latex = "\n\n".join(f"${block}$" for block in latex_blocks) if latex_blocks else ""
    question_text = re.sub(r"\s+", " ", md).strip()

    return {
        "question_text": question_text,
        "question_latex": question_latex,
        "markdown": md,
        "json": json_payload if isinstance(json_payload, dict) else {"raw": json_payload},
    }
