#!/usr/bin/env python3
"""
llm_steps_parser.py

Production-grade-ish parser for LLM math solutions:
- Fetches full Ollama streaming output
- Parses into sections -> steps -> blocks (text/math)
- Extracts final answers heuristically
- Detects truncation/incomplete output with diagnostics
- Optional auto-repair for unclosed math delimiters (render-safe)

Usage:
  # Parse existing text file:
  python llm_steps_parser.py --from-file sample.txt --out result.json

  # Call Ollama and parse:
  python llm_steps_parser.py --ollama-url http://localhost:11434 \
    --model Qwen2.5-Math-7B-Instruct-Q4_K_M:latest --prompt-file prompt.txt --out result.json

  # Print pretty preview to console:
  python llm_steps_parser.py --from-file sample.txt --preview
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

# ---- Optional dependency for Ollama HTTP calls ----
# We use requests because it's common and simple.
# Install: pip install requests
try:
    import requests  # type: ignore
except Exception:
    requests = None


# ----------------------------
# Data structures
# ----------------------------

@dataclass
class Block:
    kind: str      # "text" | "math"
    content: str

@dataclass
class Step:
    index: int
    kind: str      # "work" | "conclusion" | "note"
    blocks: List[Block]
    raw: str

@dataclass
class IncompleteDiag:
    incomplete: bool
    reasons: List[str]
    details: Dict[str, Any]
    tail: str

@dataclass
class Section:
    label: str
    heading: str
    steps: List[Step]
    final_answer: Optional[str]
    incomplete: bool
    incomplete_diag: Optional[Dict[str, Any]] = None

@dataclass
class ParseResult:
    sections: List[Section]
    global_final_answer: Optional[str]
    warnings: List[Any]  # string or dict warnings; keep flexible
    meta: Dict[str, Any]


# ----------------------------
# Cleaning / normalization
# ----------------------------

# e.g. "[答案]" at top
_GARBLED_HEADER_RE = re.compile(r"^\s*\[[^\]]{1,40}\]\s*\n+", re.UNICODE)

def clean_llm_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")

    # Remove garbled header blocks
    text = _GARBLED_HEADER_RE.sub("", text)

    # Normalize spaces but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# ----------------------------
# Section splitting
# ----------------------------

_SECTION_HEAD_RE = re.compile(r"(?m)^\s*\((?P<label>[a-zA-Z0-9]+)\)\s+")

def split_into_sections(text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (label, section_text).
    If no explicit sections, returns [("main", text)].
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
# Text vs math blocks
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
    "therefore", "thus", "hence", "final answer", "answer:", "solution is",
    "we get:", "so,", "so ", "this gives", "conclude", "we conclude"
)
_NOTE_CUES = ("note:", "remark:", "warning:", "this is not correct", "incorrect", "however")

def paragraph_split(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

def classify_step(paragraph: str) -> str:
    low = paragraph.lower()
    if any(cue in low for cue in _NOTE_CUES):
        return "note"
    if any(cue in low for cue in _CONCLUSION_CUES):
        return "conclusion"
    return "work"


# ----------------------------
# Final answer extraction heuristics
# ----------------------------

_FINAL_CUE_RE = re.compile(
    r"(?i)\b(final answer|answer|therefore|thus|hence|solution is|we conclude|so,?\s+)\b"
)

def extract_final_answer(section_text: str) -> Optional[str]:
    """
    Heuristics:
      1) Find last paragraph containing final-cue words; return last math block in it.
      2) Else return last math block in the whole section.
      3) Else return last paragraph.
    """
    paras = paragraph_split(section_text)

    cue_idxs = [i for i, p in enumerate(paras) if _FINAL_CUE_RE.search(p)]
    candidate_para = paras[cue_idxs[-1]] if cue_idxs else None

    def last_math_in(text: str) -> Optional[str]:
        blocks = split_blocks_preserve_math(text)
        for b in reversed(blocks):
            if b.kind == "math":
                return b.content
        return None

    if candidate_para:
        m = last_math_in(candidate_para)
        return m or candidate_para.strip()

    # last math in section
    blocks = split_blocks_preserve_math(section_text)
    for b in reversed(blocks):
        if b.kind == "math":
            return b.content

    return paras[-1].strip() if paras else None


# ----------------------------
# Incomplete detection + optional repair
# ----------------------------

_LATEX_BAD_TAIL_RE = re.compile(r"(\\frac\{$|\\sqrt\{$|\\left$|\\right$|=$)", re.IGNORECASE)

def detect_incomplete(text: str, tail_len: int = 240) -> IncompleteDiag:
    reasons: List[str] = []
    details: Dict[str, Any] = {}

    open_sq = text.count(r"\[")
    close_sq = text.count(r"\]")
    open_par = text.count(r"\(")
    close_par = text.count(r"\)")
    dollars = text.count("$$")

    details["math_delimiters"] = {
        r"\[": open_sq, r"\]": close_sq,
        r"\(": open_par, r"\)": close_par,
        "$$": dollars
    }

    if open_sq != close_sq:
        reasons.append("unclosed_math_block_brackets")
        details["unclosed_math_block_brackets"] = {"open": open_sq, "close": close_sq}

    if open_par != close_par:
        reasons.append("unclosed_inline_math_parens")
        details["unclosed_inline_math_parens"] = {"open": open_par, "close": close_par}

    if dollars % 2 == 1:
        reasons.append("unclosed_double_dollar_block")
        details["unclosed_double_dollar_block"] = {"count": dollars}

    stripped = text.strip()
    tail = stripped[-tail_len:] if len(stripped) > tail_len else stripped
    details["tail_len"] = tail_len

    if _LATEX_BAD_TAIL_RE.search(stripped):
        reasons.append("ends_with_incomplete_latex_command")

    # ends mid-word/sentence (rough heuristic)
    if re.search(r"[A-Za-z]\s*$", stripped) and not stripped.endswith((".", "!", "?", ")", "]", "}", "$", ".")):
        reasons.append("ends_mid_word_or_sentence")

    return IncompleteDiag(
        incomplete=len(reasons) > 0,
        reasons=reasons,
        details=details,
        tail=tail
    )

def auto_close_math_delimiters(text: str) -> str:
    """
    Safe for rendering only. Does NOT claim correctness.
    Only appends closing delimiters if imbalance detected.
    """
    open_sq = text.count(r"\[")
    close_sq = text.count(r"\]")
    open_par = text.count(r"\(")
    close_par = text.count(r"\)")
    dollars = text.count("$$")

    out = text
    if open_sq > close_sq:
        out += "\n\\]"
    if open_par > close_par:
        out += "\n\\)"
    if dollars % 2 == 1:
        out += "\n$$"
    return out


# ----------------------------
# Main parse function
# ----------------------------

def parse_llm_solution(
    raw_text: str,
    *,
    auto_repair_for_render: bool = False,
    strict_final_answer_when_incomplete: bool = False
) -> ParseResult:
    warnings: List[Any] = []
    meta: Dict[str, Any] = {}

    cleaned = clean_llm_text(raw_text)
    meta["cleaned_chars"] = len(cleaned)

    secs_raw = split_into_sections(cleaned)
    sections: List[Section] = []

    for label, sec_text in secs_raw:
        diag = detect_incomplete(sec_text)

        # Optionally auto-repair delimiters so KaTeX/MathJax won't crash
        sec_text_for_parse = auto_close_math_delimiters(sec_text) if auto_repair_for_render else sec_text

        paras = paragraph_split(sec_text_for_parse)
        steps: List[Step] = []
        for i, p in enumerate(paras, start=1):
            blocks = split_blocks_preserve_math(p)
            steps.append(Step(index=i, kind=classify_step(p), blocks=blocks, raw=p))

        final_answer = extract_final_answer(sec_text_for_parse)

        # If incomplete and strict, blank final answer (avoid misleading "final")
        if diag.incomplete and strict_final_answer_when_incomplete:
            final_answer = None

        heading = f"({label})" if label != "main" else "main"

        section = Section(
            label=str(label),
            heading=heading,
            steps=steps,
            final_answer=final_answer,
            incomplete=diag.incomplete,
            incomplete_diag={
                "reasons": diag.reasons,
                "details": diag.details,
                "tail": diag.tail
            } if diag.incomplete else None
        )
        sections.append(section)

        if diag.incomplete:
            warnings.append({
                "type": "section_incomplete",
                "section": str(label),
                "reasons": diag.reasons,
                "tail": diag.tail[:240]
            })

    # Global final answer: last section's final answer
    global_final = None
    for s in reversed(sections):
        if s.final_answer:
            global_final = s.final_answer
            break

    return ParseResult(
        sections=sections,
        global_final_answer=global_final,
        warnings=warnings,
        meta=meta
    )


# ----------------------------
# Ollama: fetch full output (streaming)
# ----------------------------

def ollama_generate_full(
    base_url: str,
    model: str,
    prompt: str,
    *,
    options: Optional[Dict[str, Any]] = None,
    timeout_s: int = 180
) -> str:
    """
    Reads streaming JSON lines from /api/generate until {"done": true}.
    Returns concatenated "response" text.
    """
    if requests is None:
        raise RuntimeError("requests not installed. Run: pip install requests")

    url = f"{base_url.rstrip('/')}/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }
    if options:
        payload["options"] = options

    chunks: List[str] = []
    with requests.post(url, json=payload, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            obj = json.loads(line)
            chunks.append(obj.get("response", ""))
            if obj.get("done", False):
                break

    return "".join(chunks)


# ----------------------------
# Output helpers
# ----------------------------

def to_json(obj: Any) -> str:
    def convert(x: Any) -> Any:
        if hasattr(x, "__dataclass_fields__"):
            return {k: convert(v) for k, v in asdict(x).items()}
        if isinstance(x, list):
            return [convert(i) for i in x]
        if isinstance(x, dict):
            return {k: convert(v) for k, v in x.items()}
        return x
    return json.dumps(convert(obj), indent=2, ensure_ascii=False)

def preview_console(result: ParseResult, max_steps: int = 5) -> None:
    for sec in result.sections:
        print(f"\nSECTION {sec.heading} incomplete={sec.incomplete}")
        if sec.incomplete and sec.incomplete_diag:
            print(f"  reasons: {sec.incomplete_diag['reasons']}")
            print(f"  tail: {sec.incomplete_diag['tail'][:120]!r}")
        for step in sec.steps[:max_steps]:
            print(f"  Step {step.index} [{step.kind}]")
            for b in step.blocks:
                short = b.content
                if len(short) > 120:
                    short = short[:117] + "..."
                print(f"    - {b.kind}: {short}")
        if len(sec.steps) > max_steps:
            print(f"  ... ({len(sec.steps) - max_steps} more steps)")
        print(f"  final_answer: {sec.final_answer!r}")

    if result.warnings:
        print("\nWARNINGS:")
        for w in result.warnings:
            print(f"  - {w}")


def _extract_boxed_answer(text: str) -> Optional[str]:
    src = str(text or "")
    key = "\\boxed{"
    start = src.rfind(key)
    if start == -1:
        return None
    i = start + len(key)
    depth = 1
    out: List[str] = []
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
        i += 1
    candidate = "".join(out).strip()
    return candidate or None


def _strip_latex(text: str) -> str:
    out = str(text or "")
    out = re.sub(r"\$\$(.+?)\$\$", "", out, flags=re.DOTALL)
    out = re.sub(r"\\\[(.+?)\\\]", "", out, flags=re.DOTALL)
    out = re.sub(r"\\\((.+?)\\\)", "", out, flags=re.DOTALL)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def build_short_tier_extraction(
    raw_text: str,
    *,
    question_text: str = "",
    question_id: str = "q1",
    mode: str = "SOLVE",
) -> Dict[str, Any]:
    parsed = parse_llm_solution(str(raw_text or ""))
    raw_user_extraction = asdict(parsed)

    steps: List[Dict[str, Any]] = []
    step_index = 1
    for sec in parsed.sections:
        for st in sec.steps:
            math_latex = [str(b.content or "").strip() for b in st.blocks if b.kind == "math" and str(b.content or "").strip()]
            steps.append(
                {
                    "index": step_index,
                    "title": sec.heading if sec.heading != "main" else f"Step {step_index}",
                    "explanation": str(st.raw or "").strip(),
                    "math_latex": math_latex[:12],
                }
            )
            step_index += 1

    boxed_from_raw = _extract_boxed_answer(raw_text)
    final_latex = str(parsed.global_final_answer or "").strip()
    if boxed_from_raw:
        final_latex = f"\\boxed{{{boxed_from_raw}}}"
    answer_text = _strip_latex(final_latex)
    if not answer_text and boxed_from_raw:
        answer_text = boxed_from_raw
    if answer_text.startswith("\\boxed{") and answer_text.endswith("}"):
        inner = _extract_boxed_answer(answer_text)
        if inner:
            answer_text = inner

    values: List[Dict[str, Any]] = []
    if boxed_from_raw and re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", boxed_from_raw):
        values.append({"label": "boxed_1", "value": float(boxed_from_raw), "value_latex": None})

    question_text_clean = str(question_text or "").strip()
    question_id_clean = str(question_id or "").strip() or "q1"
    question_obj = {"id": question_id_clean, "text": question_text_clean, "mode": str(mode or "SOLVE").upper()}
    if question_text_clean:
        raw_user_extraction["question"] = question_obj

    payload: Dict[str, Any] = {
        "steps": steps,
        "final_answer": {
            "answer_text": answer_text[:4000],
            "answer_latex": final_latex,
            "values": values,
            "units": None,
        },
        "raw_user_extraction": raw_user_extraction,
    }
    if question_text_clean:
        payload["question"] = question_obj
        payload["problem"] = {
            "original_text": question_text_clean,
            "recognized_text": question_text_clean,
            "statement": question_text_clean,
        }
    return payload


# ----------------------------
# CLI
# ----------------------------

def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _write_file(path: str, data: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-file", help="Path to a text file containing the LLM output")
    src.add_argument("--ollama", action="store_true", help="Call Ollama and parse its output")

    p.add_argument("--out", help="Write JSON output to this file (or stdout if omitted)")
    p.add_argument("--preview", action="store_true", help="Print a console preview of parsed steps")
    p.add_argument("--auto-repair", action="store_true", help="Auto-close math delimiters for safer rendering")
    p.add_argument("--strict-final", action="store_true", help="If incomplete, blank final_answer to avoid misleading UI")

    # Ollama args
    p.add_argument("--ollama-url", default="http://localhost:11434")
    p.add_argument("--model", help="Ollama model name, e.g. Qwen2.5-Math-7B-Instruct-Q4_K_M:latest")
    p.add_argument("--prompt-file", help="Text file containing the prompt to send to Ollama")
    p.add_argument("--prompt", help="Prompt string (if not using --prompt-file)")
    p.add_argument("--num-predict", type=int, default=None, help="Ollama options.num_predict (increase to avoid truncation)")
    p.add_argument("--temperature", type=float, default=None, help="Ollama options.temperature")
    p.add_argument("--timeout", type=int, default=180, help="HTTP timeout seconds")

    args = p.parse_args(argv)

    # Load raw text
    if args.from_file:
        raw_text = _read_file(args.from_file)
    else:
        # ollama path
        if not args.model:
            print("ERROR: --model is required with --ollama", file=sys.stderr)
            return 2
        prompt = args.prompt or (_read_file(args.prompt_file) if args.prompt_file else None)
        if not prompt:
            print("ERROR: provide --prompt or --prompt-file with --ollama", file=sys.stderr)
            return 2

        options: Dict[str, Any] = {}
        if args.num_predict is not None:
            options["num_predict"] = args.num_predict
        if args.temperature is not None:
            options["temperature"] = args.temperature

        raw_text = ollama_generate_full(
            args.ollama_url,
            args.model,
            prompt,
            options=options or None,
            timeout_s=args.timeout
        )

    # Parse
    result = parse_llm_solution(
        raw_text,
        auto_repair_for_render=args.auto_repair,
        strict_final_answer_when_incomplete=args.strict_final
    )

    # Output
    out_json = to_json(result)
    if args.out:
        _write_file(args.out, out_json)
    else:
        print(out_json)

    if args.preview:
        preview_console(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
