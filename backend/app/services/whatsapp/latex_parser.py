import re
import hashlib
from typing import List, Dict, Tuple


BLOCK_PATTERNS = [
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
    re.compile(r"\\begin\{([a-zA-Z*]+)\}(.+?)\\end\{\1\}", re.DOTALL),
]

INLINE_PATTERN = re.compile(r"\\\((.+?)\\\)")


def normalize_latex(latex: str) -> str:
    if not latex:
        return ""
    out = latex.strip()
    out = re.sub(r"\s+", " ", out)
    return out


def extract_latex(text: str) -> Tuple[List[Dict[str, str]], str]:
    if not text:
        return [], ""

    matches = []
    occupied = []

    for pat in BLOCK_PATTERNS:
        for m in pat.finditer(text):
            matches.append({"type": "block", "latex": m.group(0), "start": m.start(), "end": m.end()})
            occupied.append((m.start(), m.end()))

    for m in INLINE_PATTERN.finditer(text):
        if any(s <= m.start() < e for s, e in occupied):
            continue
        matches.append({"type": "inline", "latex": m.group(0), "start": m.start(), "end": m.end()})

    matches.sort(key=lambda x: x["start"])

    plain = []
    last = 0
    eq_idx = 1
    for m in matches:
        plain.append(text[last:m["start"]])
        plain.append(f"[EQ_{eq_idx}]")
        eq_idx += 1
        last = m["end"]
    plain.append(text[last:])

    plain_text = "".join(plain)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()

    # Strip delimiters for renderer
    cleaned = []
    for m in matches:
        latex = m["latex"]
        if latex.startswith("$$") and latex.endswith("$$"):
            latex = latex[2:-2].strip()
        elif latex.startswith("\\[") and latex.endswith("\\]"):
            latex = latex[2:-2].strip()
        elif latex.startswith("\\(") and latex.endswith("\\)"):
            latex = latex[2:-2].strip()
        cleaned.append({"type": m["type"], "latex": normalize_latex(latex)})

    return cleaned, plain_text


def make_latex_cache_key(latex: str, engine: str, image_format: str, display_mode: bool) -> str:
    normalized = normalize_latex(latex)
    raw = f"{engine}|{image_format}|{int(display_mode)}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
