from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Any


# ----------------------------
# Data structures
# ----------------------------

@dataclass
class Block:
    kind: str  # "text" | "math"
    content: str

@dataclass
class Step:
    index: int
    kind: str  # "work" | "conclusion" | "note"
    blocks: List[Block]
    raw: str

@dataclass
class Section:
    label: str                 # e.g. "a", "b", "c" or "main"
    heading: str               # e.g. "(a)"
    steps: List[Step]
    final_answer: Optional[str]
    incomplete: bool

@dataclass
class ParseResult:
    sections: List[Section]
    global_final_answer: Optional[str]
    warnings: List[str]


# ----------------------------
# Cleaning / normalization
# ----------------------------

_GARBLED_HEADER_RE = re.compile(r"^\s*\[[^\]]{1,40}\]\s*\n+", re.UNICODE)

def clean_llm_text(text: str) -> str:
    # Normalize newlines and unicode
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)

    # Remove common "garbled header" blocks like [ç­”æ¡ˆ]
    text = _GARBLED_HEADER_RE.sub("", text)

    # Remove zero-width / non-printing junk that sometimes appears
    text = text.replace("\u200b", "").replace("\ufeff", "")

    # Collapse excessive whitespace (but keep paragraph breaks)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


# ----------------------------
# Section splitting ( (a), (b), (1), etc. )
# ----------------------------

_SECTION_HEAD_RE = re.compile(r"(?m)^\s*\((?P<label>[a-zA-Z0-9]+)\)\s+")

def split_into_sections(text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (label, section_text). If no explicit sections, returns [("main", text)].
    """
    matches = list(_SECTION_HEAD_RE.finditer(text))
    if not matches:
        return [("main", text)]

    sections: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        label = m.group("label")
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sec_text = text[start:end].strip()
        sections.append((label, sec_text))
    return sections


# ----------------------------
# Tokenization into text vs math blocks
# ----------------------------

# Capture:
#  - \[ ... \]
#  - \( ... \)
#  - $$ ... $$
_MATH_BLOCK_RE = re.compile(
    r"(?s)(\\\[(?:.*?){1,}?\\\]|\\\((?:.*?){1,}?\\\)|\$\$(?:.*?){1,}?\$\$)"
)

def split_blocks_preserve_math(text: str) -> List[Block]:
    blocks: List[Block] = []
    pos = 0
    for m in _MATH_BLOCK_RE.finditer(text):
        if m.start() > pos:
            chunk = text[pos:m.start()]
            if chunk.strip():
                blocks.append(Block(kind="text", content=chunk.strip()))
        blocks.append(Block(kind="math", content=m.group(1).strip()))
        pos = m.end()

    if pos < len(text):
        tail = text[pos:]
        if tail.strip():
            blocks.append(Block(kind="text", content=tail.strip()))

    return blocks


# ----------------------------
# Step splitting (paragraph-based)
# ----------------------------

_CONCLUSION_CUES = (
    "therefore", "thus", "hence", "so,", "so ", "final answer", "answer:", "solution is", "we get:",
    "therefore,", "therefore:", "so we", "this gives", "conclude"
)

_NOTE_CUES = ("note:", "remark:", "warning:", "this is not correct", "incorrect", "however")

def classify_step(paragraph: str) -> str:
    low = paragraph.lower()
    if any(cue in low for cue in _NOTE_CUES):
        return "note"
    if any(cue in low for cue in _CONCLUSION_CUES):
        return "conclusion"
    return "work"

def paragraph_split(text: str) -> List[str]:
    # keep order, split on blank lines
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts


# ----------------------------
# Final answer extraction heuristics
# ----------------------------

_FINAL_CUE_RE = re.compile(
    r"(?i)\b(final answer|answer|therefore|thus|hence|solution is|we conclude|so,?\s+)\b"
)

def extract_final_answer(section_text: str, steps: List[Step]) -> Optional[str]:
    """
    Heuristics:
      1) Look for paragraphs containing final-cue words, prefer last such paragraph.
      2) Prefer the last math block inside that paragraph.
      3) Fallback: last math block in section.
      4) Fallback: last non-empty paragraph.
    """
    # 1) paragraphs with cues
    paras = paragraph_split(section_text)
    cue_idxs = [i for i, p in enumerate(paras) if _FINAL_CUE_RE.search(p)]
    candidate_para = paras[cue_idxs[-1]] if cue_idxs else None

    def last_math_in(text: str) -> Optional[str]:
        blks = split_blocks_preserve_math(text)
        for b in reversed(blks):
            if b.kind == "math":
                return b.content
        return None

    if candidate_para:
        m = last_math_in(candidate_para)
        if m:
            return m
        # if no math, return the paragraph trimmed (still useful)
        return candidate_para.strip()

    # 3) last math in section
    all_blocks = split_blocks_preserve_math(section_text)
    for b in reversed(all_blocks):
        if b.kind == "math":
            return b.content

    # 4) last paragraph
    return paras[-1].strip() if paras else None


# ----------------------------
# Incomplete/truncation detection
# ----------------------------

def looks_incomplete(text: str) -> bool:
    # Unclosed math delimiters are a strong hint
    open_bracket = text.count(r"\[")
    close_bracket = text.count(r"\]")
    open_paren = text.count(r"\(")
    close_paren = text.count(r"\)")
    open_dollar = text.count("$$")

    if open_bracket != close_bracket:
        return True
    if open_paren != close_paren:
        return True
    if open_dollar % 2 == 1:
        return True

    # Ends with obvious cutoff patterns
    tail = text.strip()[-20:].lower()
    if tail.endswith(("\\frac{", "\\sqrt{", "\\left", "\\right", "=")):
        return True

    # Ends mid-word
    if re.search(r"[A-Za-z]\\s*$", text):
        return True

    return False


# ----------------------------
# Main parse function
# ----------------------------

def parse_llm_solution(raw_text: str) -> ParseResult:
    warnings: List[str] = []
    text = clean_llm_text(raw_text)

    secs_raw = split_into_sections(text)
    sections: List[Section] = []

    for label, sec_text in secs_raw:
        paras = paragraph_split(sec_text)

        steps: List[Step] = []
        for i, p in enumerate(paras, start=1):
            blocks = split_blocks_preserve_math(p)
            steps.append(
                Step(
                    index=i,
                    kind=classify_step(p),
                    blocks=blocks,
                    raw=p
                )
            )

        final_answer = extract_final_answer(sec_text, steps)
        incomplete = looks_incomplete(sec_text)

        heading = f"({label})" if label != "main" else "main"
        sections.append(
            Section(
                label=str(label),
                heading=heading,
                steps=steps,
                final_answer=final_answer,
                incomplete=incomplete
            )
        )

    # Global final answer: take the last section's final answer if any
    global_final = None
    for s in reversed(sections):
        if s.final_answer:
            global_final = s.final_answer
            break

    # Add warning if any section incomplete
    if any(s.incomplete for s in sections):
        warnings.append("Model output looks truncated or has unclosed math delimiters in at least one section.")

    return ParseResult(sections=sections, global_final_answer=global_final, warnings=warnings)


# ----------------------------
# Convenience: JSON export
# ----------------------------

def to_json(result: ParseResult) -> str:
    def convert(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return {k: convert(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [convert(x) for x in obj]
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        return obj

    payload = convert(result)
    return json.dumps(payload, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) >= 2:
        in_path = Path(sys.argv[1])
        out_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path("ollama_short_live_diffeq_extracted_usercode.json")
        raw = in_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_llm_solution(raw)
        out_path.write_text(to_json(parsed), encoding="utf-8")
        print(f"WROTE {out_path}")
    else:
        sample = """[ç­”æ¡ˆ]

(a) To solve for \\( x(t) \\) explicitly, we need to find both the homogeneous solution (transient) and the particular solution (steady-state).

First, let's find the homogeneous solution by solving the characteristic equation:
\\[ 2r^2 + 6r + 18 = 0. \\]
...
"""
        parsed = parse_llm_solution(sample)
        print(to_json(parsed))
