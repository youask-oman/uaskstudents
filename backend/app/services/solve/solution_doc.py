from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from sympy import Eq, S, Symbol, preorder_traversal, solve, sqrt
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


_SECTION_HEADER_RE = re.compile(
    r"^\s*#\s+(Recognized Problem|Domain Constraints|Steps|Graphs|Verification|Final Answer)\s*$",
    re.IGNORECASE,
)
_STEP_HEADER_STRICT_RE = re.compile(r"^\s*##\s*Step\s+(\d+):\s+(.+?)\s*$", re.IGNORECASE)
_STEP_HEADER_LOOSE_RE = re.compile(r"^\s*(?:##\s*)?Step\s+(\d+):\s+(.+?)\s*$", re.IGNORECASE)
_PLOT_SENTINEL_RE = re.compile(r"^\s*PLOTLY_JSON:\s*([A-Za-z0-9._:-]+)\s*$", re.IGNORECASE)
_PLOTLY_FENCE_RE = re.compile(r"```(?:plotly|json)\s*\n([\s\S]*?)```", re.IGNORECASE)

_UNSAFE_MACRO_RE = re.compile(
    r"\\(?:require|html(?:Class|Id|Style|Data)?|includegraphics|input|write18)\b",
    re.IGNORECASE,
)
_FINAL_ANSWER_RE = re.compile(r"^\s*Final\s*Answer\s*:\s*(.+?)\s*$", re.IGNORECASE)
_FINAL_LATEX_RE = re.compile(r"^\s*LaTeX\s*:\s*(.+?)\s*$", re.IGNORECASE)
_FINAL_TEXT_BOLD_RE = re.compile(r"^\s*\*\*Text:\*\*\s*(.+?)\s*$", re.IGNORECASE)
_FINAL_LATEX_BOLD_RE = re.compile(r"^\s*\*\*LaTeX:\*\*\s*(.+?)\s*$", re.IGNORECASE)
_FINAL_TEXT_PLAIN_RE = re.compile(r"^\s*Text\s*:\s*(.+?)\s*$", re.IGNORECASE)
_FINAL_ANSWER_PLACEHOLDER_RE = re.compile(r"^(?:n/?a|none|null|not\s+provided|unknown|-+)$", re.IGNORECASE)
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*\u2022]|\(\d+\)|\d+[.)])\s*")
_CODE_FENCE_RE = re.compile(r"```([a-zA-Z0-9_-]*)\s*\n([\s\S]*?)```")

_MOJIBAKE_REPLACEMENTS = {
    "\u00e2\u20ac\u00a2": "\u2022",
    "\u00e2\u20ac\u201d": "\u2014",
    "\u00e2\u20ac\u201c": "\u2013",
    "\u00e2\u2030\u00a5": "\u2265",
    "\u00e2\u2030\u00a4": "\u2264",
    "\u00e2\u2030\u00a0": "\u2260",
    "\u00e2\u02c6\u02c6": "\u2208",
    "\u00e2\u2020\u2019": "\u2192",
}


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        item = (value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _repair_mojibake(text: str) -> str:
    out = text or ""
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        out = out.replace(bad, good)
    return out


def _strip_unsafe_latex_macros(text: str) -> str:
    return _UNSAFE_MACRO_RE.sub("", text or "")


def _repair_sqrt_forms(text: str) -> str:
    out = text
    out = re.sub(r"\\sqrt\s*\(([^()]+)\)", r"\\sqrt{\1}", out)
    out = re.sub(r"\\sqrt\s+([A-Za-z0-9]+)", r"\\sqrt{\1}", out)
    return out


def _normalize_frac_shortcuts(text: str) -> str:
    return re.sub(r"\\frac\s*([A-Za-z0-9])\s*([A-Za-z0-9])", r"\\frac{\1}{\2}", text)


def _strip_illegal_line_breaks(text: str) -> str:
    lines = (text or "").splitlines()
    out: List[str] = []
    in_align_env = False
    for raw in lines:
        line = raw
        if re.search(r"\\begin\{(?:align|aligned|array|matrix|bmatrix|pmatrix)\*?\}", line):
            in_align_env = True
        if re.search(r"\\end\{(?:align|aligned|array|matrix|bmatrix|pmatrix)\*?\}", line):
            in_align_env = False

        if not in_align_env:
            stripped = line.strip()
            if stripped == r"\\":
                continue
            if re.search(r"\\\s*$", line):
                line = re.sub(r"\\\s*$", "", line)
        out.append(line)
    return "\n".join(out)


def _escape_unmatched_dollars(text: str) -> str:
    chars = list(text)
    dollar_positions = [idx for idx, ch in enumerate(chars) if ch == "$" and (idx == 0 or chars[idx - 1] != "\\")]
    if len(dollar_positions) % 2 == 0:
        return text
    last = dollar_positions[-1]
    chars[last] = r"\$"
    return "".join(chars)


def _space_wrapped_inline_math(text: str) -> str:
    return re.sub(r"([A-Za-z0-9])\$(.+?)(?<!\\)\$([A-Za-z0-9])", r"\1 $\2$ \3", text, flags=re.DOTALL)


def latex_normalize_with_report(text: str) -> Tuple[str, List[str]]:
    report: List[str] = []
    out = text or ""

    next_out = _repair_mojibake(out)
    if next_out != out:
        report.append("repaired_common_mojibake_sequences")
    out = next_out

    next_out = out.replace("\r\n", "\n").replace("\r", "\n")
    if next_out != out:
        report.append("normalized_newlines_to_lf")
    out = next_out

    next_out = _strip_unsafe_latex_macros(out)
    if next_out != out:
        report.append("removed_unsafe_latex_macros")
    out = next_out

    next_out = out.replace("\\[", "$$").replace("\\]", "$$")
    if next_out != out:
        report.append("converted_display_delimiters_to_double_dollar")
    out = next_out

    next_out = out.replace("\\(", "$").replace("\\)", "$")
    if next_out != out:
        report.append("converted_inline_delimiters_to_single_dollar")
    out = next_out

    next_out = _repair_sqrt_forms(out)
    if next_out != out:
        report.append("repaired_common_sqrt_forms")
    out = next_out

    next_out = _normalize_frac_shortcuts(out)
    if next_out != out:
        report.append("normalized_frac_shortcuts")
    out = next_out

    next_out = _strip_illegal_line_breaks(out)
    if next_out != out:
        report.append("removed_illegal_latex_line_breaks_outside_aligned")
    out = next_out

    next_out = _space_wrapped_inline_math(out)
    if next_out != out:
        report.append("inserted_missing_spaces_around_inline_math")
    out = next_out

    next_out = _escape_unmatched_dollars(out)
    if next_out != out:
        report.append("escaped_unmatched_dollar_delimiter")
    out = next_out
    return out, report


def latex_normalize(text: str) -> str:
    normalized, _ = latex_normalize_with_report(text)
    return normalized


def _new_doc(problem_text: str, raw_text: str) -> Dict[str, Any]:
    problem = (problem_text or "").strip()
    return {
        "recognized_problem": {
            "text": problem or "Unknown problem",
            "latex": problem or None,
        },
        "domain_constraints": [],
        "steps": [],
        "plots": [],
        "verification": [],
        "final_answer": {"text": "", "latex": ""},
        "autocorrect": {"applied": False},
        "parse_errors": [],
        "latex_normalization_report": [],
        "raw_output_markdown": raw_text or "",
        "raw_fallback": raw_text or "",
        "parse_status": "failed",
    }


def _to_parse_status(steps: List[Dict[str, Any]], final_text: str, final_latex: str) -> str:
    if steps and (final_text or final_latex):
        return "ok"
    if steps or final_text or final_latex:
        return "partial"
    return "failed"


def _doc_has_meaningful_content(doc: Dict[str, Any]) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("steps"):
        return True
    if doc.get("plots"):
        return True
    if doc.get("domain_constraints"):
        return True
    if doc.get("verification"):
        return True
    final = doc.get("final_answer") or {}
    final_text = str(final.get("text") or "").strip()
    final_latex = str(final.get("latex") or "").strip()
    if final_text and not _FINAL_ANSWER_PLACEHOLDER_RE.match(final_text):
        return True
    if final_latex and not _FINAL_ANSWER_PLACEHOLDER_RE.match(final_latex):
        return True
    return False


def _strip_math_delimiters(value: str) -> str:
    item = (value or "").strip()
    if item.startswith("$$") and item.endswith("$$") and len(item) >= 4:
        return item[2:-2].strip()
    if item.startswith("$") and item.endswith("$") and len(item) >= 2:
        return item[1:-1].strip()
    return item


def _normalize_constraint_item(value: str) -> str:
    item = (value or "").strip()
    if not item:
        return ""
    wrapped = re.match(r"^\$\s*(.*?)\s*\$$", item)
    if wrapped:
        item = f"${wrapped.group(1).strip()}$"
    item = re.sub(r"\s{2,}", " ", item).strip()
    return item


def _is_valid_plotly_payload(payload: Dict[str, Any]) -> bool:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return False
    for trace in data:
        if not isinstance(trace, dict):
            return False
        trace_type = str(trace.get("type") or "scatter").strip().lower()
        if trace_type in {"scatter", "line", "bar"}:
            xs = trace.get("x")
            ys = trace.get("y")
            if not isinstance(xs, list) or not isinstance(ys, list) or len(xs) != len(ys) or not xs:
                return False
    return True


def _parse_plotly_fences(text: str, *, error_prefix: str = "plotly") -> Tuple[List[Dict[str, Any]], List[str]]:
    plots: List[Dict[str, Any]] = []
    errors: List[str] = []
    idx = 0
    for block_idx, match in enumerate(_CODE_FENCE_RE.finditer(text or ""), start=1):
        language = (match.group(1) or "").strip().lower()
        payload_text = (match.group(2) or "").strip()
        if language not in {"plotly", "json"}:
            continue
        if not payload_text:
            errors.append(f"{error_prefix}: fenced block {block_idx} is empty")
            continue
        try:
            payload = json.loads(payload_text)
        except Exception as exc:
            errors.append(f"{error_prefix}: fenced block {block_idx} invalid JSON ({exc})")
            continue
        if isinstance(payload, dict) and _is_valid_plotly_payload(payload):
            idx += 1
            plots.append({"id": f"plot_{idx}", "plotly": payload})
        else:
            errors.append(f"{error_prefix}: fenced block {block_idx} is not a valid Plotly payload")
    return plots, errors


def _extract_fenced_json_after(lines: List[str], start_idx: int) -> Tuple[Optional[Dict[str, Any]], int]:
    idx = start_idx + 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines) or not lines[idx].strip().startswith("```"):
        return None, start_idx
    idx += 1
    collected: List[str] = []
    while idx < len(lines) and not lines[idx].strip().startswith("```"):
        collected.append(lines[idx])
        idx += 1
    if idx >= len(lines):
        return None, start_idx
    payload = "\n".join(collected).strip()
    try:
        parsed = json.loads(payload)
    except Exception:
        return None, idx
    if isinstance(parsed, dict):
        return parsed, idx
    return None, idx


def _extract_sections_from_markdown(text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for raw_line in (text or "").splitlines():
        match = _SECTION_HEADER_RE.match(raw_line)
        if match:
            current = match.group(1).strip().lower().replace(" ", "_")
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(raw_line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _parse_markdown_steps(steps_section: str) -> List[Dict[str, Any]]:
    def _collect_with_regex(pattern: re.Pattern[str]) -> List[Dict[str, Any]]:
        def _finalize(step_row: Dict[str, Any]) -> Dict[str, Any]:
            body_lines = step_row.pop("body_lines")
            if body_lines:
                first = body_lines[0].strip()
                duplicated = _STEP_HEADER_LOOSE_RE.match(first)
                if duplicated and int(duplicated.group(1)) == int(step_row.get("k") or 0):
                    body_lines = body_lines[1:]
            step_row["body_markdown"] = "\n".join(body_lines).strip()
            return step_row

        parsed_steps: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for raw_line in (steps_section or "").splitlines():
            header = pattern.match(raw_line.rstrip())
            if header:
                if current:
                    parsed_steps.append(_finalize(current))
                current = {
                    "k": int(header.group(1)),
                    "title": header.group(2).strip(),
                    "body_lines": [],
                }
                continue
            if current is not None:
                current["body_lines"].append(raw_line.rstrip())
        if current:
            parsed_steps.append(_finalize(current))
        return parsed_steps

    strict_steps = _collect_with_regex(_STEP_HEADER_STRICT_RE)
    if strict_steps:
        return strict_steps
    return _collect_with_regex(_STEP_HEADER_LOOSE_RE)


def _parse_markdown_final_answer(section: str) -> Dict[str, str]:
    final_text = ""
    final_latex = ""
    for raw_line in (section or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        bold_text = _FINAL_TEXT_BOLD_RE.match(line)
        if bold_text:
            final_text = bold_text.group(1).strip()
            continue
        plain_text = _FINAL_TEXT_PLAIN_RE.match(line)
        if plain_text:
            final_text = plain_text.group(1).strip()
            continue
        bold_latex = _FINAL_LATEX_BOLD_RE.match(line)
        if bold_latex:
            final_latex = _strip_math_delimiters(bold_latex.group(1))
            continue
        simple_text = _FINAL_ANSWER_RE.match(line)
        if simple_text:
            final_text = simple_text.group(1).strip()
            continue
        simple_latex = _FINAL_LATEX_RE.match(line)
        if simple_latex:
            final_latex = _strip_math_delimiters(simple_latex.group(1))
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_text or ""):
        final_text = ""
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_latex or ""):
        final_latex = ""
    return {"text": final_text, "latex": final_latex}


def _parse_markdown_solution(text: str, problem_text: str) -> Optional[Dict[str, Any]]:
    sections = _extract_sections_from_markdown(text)
    if not sections:
        return None

    doc = _new_doc(problem_text, text)
    recognized = sections.get("recognized_problem", "").strip()
    doc["recognized_problem"] = {
        "text": recognized or doc["recognized_problem"]["text"],
        "latex": (problem_text or "").strip() or recognized or doc["recognized_problem"]["latex"],
    }

    domain_constraints: List[str] = []
    for line in sections.get("domain_constraints", "").splitlines():
        cleaned = _normalize_constraint_item(_BULLET_PREFIX_RE.sub("", line).strip())
        if cleaned and cleaned.lower() != "none" and not _FINAL_ANSWER_PLACEHOLDER_RE.match(cleaned):
            domain_constraints.append(cleaned)
    doc["domain_constraints"] = _dedupe_preserve_order(domain_constraints)

    steps_section = sections.get("steps", "")
    steps = _parse_markdown_steps(steps_section)
    if not steps and steps_section.strip():
        non_empty_lines = [line.strip() for line in steps_section.splitlines() if line.strip()]
        has_non_placeholder = any(
            not _FINAL_ANSWER_PLACEHOLDER_RE.match(_BULLET_PREFIX_RE.sub("", line).strip())
            for line in non_empty_lines
        )
        if has_non_placeholder:
            doc["parse_errors"].append("steps: no step headers matched expected format")
    doc["steps"] = steps

    verification: List[str] = []
    for line in sections.get("verification", "").splitlines():
        cleaned = _BULLET_PREFIX_RE.sub("", line).strip()
        if cleaned and cleaned.lower() != "none" and not _FINAL_ANSWER_PLACEHOLDER_RE.match(cleaned):
            verification.append(cleaned)
    doc["verification"] = verification

    plots, plot_errors = _parse_plotly_fences(text, error_prefix="markdown_plotly")
    doc["plots"] = plots
    doc["parse_errors"].extend(plot_errors)

    final_answer = _parse_markdown_final_answer(sections.get("final_answer", ""))
    if not final_answer.get("text") and not final_answer.get("latex"):
        for line in (sections.get("final_answer", "") or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _FINAL_ANSWER_RE.match(stripped)
            if match:
                candidate = match.group(1).strip()
                if not _FINAL_ANSWER_PLACEHOLDER_RE.match(candidate):
                    final_answer["text"] = candidate
                    break
        for line in (sections.get("final_answer", "") or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _FINAL_LATEX_RE.match(stripped)
            if match:
                candidate = _strip_math_delimiters(match.group(1).strip())
                if not _FINAL_ANSWER_PLACEHOLDER_RE.match(candidate):
                    final_answer["latex"] = candidate
                    break
    doc["final_answer"] = final_answer

    doc["parse_status"] = _to_parse_status(steps, final_answer.get("text", ""), final_answer.get("latex", ""))
    if doc["parse_status"] == "failed" and any((value or "").strip() for value in sections.values()):
        doc["parse_status"] = "partial"
    return doc


def _normalize_domain_raw(value: Any) -> List[str]:
    if isinstance(value, list):
        normalized = [_normalize_constraint_item(str(item)) for item in value if str(item).strip()]
        return _dedupe_preserve_order([item for item in normalized if item])
    if isinstance(value, str):
        rows: List[str] = []
        for line in value.splitlines():
            cleaned = _normalize_constraint_item(_BULLET_PREFIX_RE.sub("", line).strip())
            if cleaned:
                rows.append(cleaned)
        return _dedupe_preserve_order(rows)
    return []


def _normalize_step_item(value: Any, index: int) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        k = int(value.get("k") or index)
        title = str(value.get("title") or f"Step {k}").strip()
        body = str(value.get("body_markdown") or value.get("body") or value.get("explanation") or "").strip()
        return {"k": k, "title": title, "body_markdown": body}

    line = str(value or "").strip()
    if not line:
        return None
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(line):
        return None

    step_match = _STEP_HEADER_LOOSE_RE.match(line)
    if step_match:
        return {"k": int(step_match.group(1)), "title": step_match.group(2).strip(), "body_markdown": ""}

    typed = re.match(r"^Step\s+(\d+):\s*(.+?)\s+[\u2014-]\s+(.+)$", line, flags=re.IGNORECASE)
    if typed:
        return {
            "k": int(typed.group(1)),
            "title": typed.group(2).strip(),
            "body_markdown": typed.group(3).strip(),
        }

    return {"k": index, "title": f"Step {index}", "body_markdown": line}


def _parse_json_solution(raw_text: str, problem_text: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads((raw_text or "").strip())
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None

    doc = _new_doc(problem_text, raw_text)
    doc["domain_constraints"] = _normalize_domain_raw(parsed.get("domain_constraints") or parsed.get("domain"))

    steps: List[Dict[str, Any]] = []
    steps_raw = parsed.get("steps")
    if isinstance(steps_raw, list):
        for idx, item in enumerate(steps_raw, start=1):
            normalized = _normalize_step_item(item, idx)
            if normalized:
                steps.append(normalized)
    doc["steps"] = steps

    verification_raw = parsed.get("verification")
    if isinstance(verification_raw, list):
        doc["verification"] = [str(v).strip() for v in verification_raw if str(v).strip()]
    elif isinstance(verification_raw, dict):
        doc["verification"] = [str(v).strip() for v in verification_raw.values() if str(v).strip()]
    elif isinstance(verification_raw, str):
        doc["verification"] = [line.strip() for line in verification_raw.splitlines() if line.strip()]

    final_text = ""
    final_latex = ""
    final_raw = parsed.get("final_answer")
    if isinstance(final_raw, dict):
        final_text = str(final_raw.get("text") or "").strip()
        final_latex = _strip_math_delimiters(str(final_raw.get("latex") or "").strip())
    elif isinstance(final_raw, str):
        final_text = _FINAL_ANSWER_RE.sub(r"\1", final_raw).strip()
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_text or ""):
        final_text = ""
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_latex or ""):
        final_latex = ""
    doc["final_answer"] = {"text": final_text, "latex": final_latex}

    plots: List[Dict[str, Any]] = []
    plotly_raw = parsed.get("plotly_json")
    if isinstance(plotly_raw, dict) and _is_valid_plotly_payload(plotly_raw):
        plots.append({"id": "plot_1", "plotly": plotly_raw})
    elif isinstance(plotly_raw, dict):
        doc["parse_errors"].append("json_plotly: plotly_json object is invalid")
    elif isinstance(plotly_raw, list):
        for idx, candidate in enumerate(plotly_raw, start=1):
            if isinstance(candidate, dict) and _is_valid_plotly_payload(candidate):
                plots.append({"id": f"plot_{idx}", "plotly": candidate})
            else:
                doc["parse_errors"].append(f"json_plotly: plotly_json[{idx}] is invalid")
    fence_plots, fence_errors = _parse_plotly_fences(raw_text, error_prefix="json_plotly")
    plots.extend(fence_plots)
    doc["parse_errors"].extend(fence_errors)
    doc["plots"] = plots

    doc["parse_status"] = _to_parse_status(steps, final_text, final_latex)
    return doc


def _parse_legacy_blob(raw_text: str, problem_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text or ("\"steps\"" not in raw_text and "\"final_answer\"" not in raw_text):
        return None

    doc = _new_doc(problem_text, raw_text)

    domain_constraints: List[str] = []
    domain_match = re.search(
        r'"domain_constraints"\s*:\s*"([\s\S]*?)"\s*,\s*"steps"',
        raw_text,
        flags=re.IGNORECASE,
    )
    if domain_match:
        domain_raw = domain_match.group(1).replace("\\n", "\n")
        for line in domain_raw.splitlines():
            cleaned = _normalize_constraint_item(_BULLET_PREFIX_RE.sub("", line).strip())
            if cleaned:
                domain_constraints.append(cleaned)
    doc["domain_constraints"] = _dedupe_preserve_order(domain_constraints)

    steps: List[Dict[str, Any]] = []
    for step_match in re.finditer(r'"Step\s+(\d+):\s*([^"]+)"', raw_text, flags=re.IGNORECASE):
        k = int(step_match.group(1))
        payload = step_match.group(2).replace("\\n", "\n").strip()
        title = f"Step {k}"
        body = payload
        split_match = re.split(r"\s+[\u2014-]\s+", payload, maxsplit=1)
        if len(split_match) == 2:
            title = split_match[0].strip() or title
            body = split_match[1].strip() or body
        steps.append({"k": k, "title": title, "body_markdown": body})
    doc["steps"] = sorted(steps, key=lambda row: int(row.get("k") or 0))

    verification: List[str] = []
    for key in ("domain_check", "substitution_check", "extraneous_or_edge_case_rejection"):
        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', raw_text, flags=re.IGNORECASE)
        if match:
            verification.append(match.group(1).replace("\\n", "\n").strip())
    doc["verification"] = verification

    final_text = ""
    final_latex = ""
    final_match = re.search(r'"final_answer"\s*:\s*"([^"]+)"', raw_text, flags=re.IGNORECASE)
    if final_match:
        final_text = _FINAL_ANSWER_RE.sub(r"\1", final_match.group(1)).strip()
    latex_match = re.search(r'"latex"\s*:\s*"([^"]+)"', raw_text, flags=re.IGNORECASE)
    if latex_match:
        final_latex = _strip_math_delimiters(latex_match.group(1).strip())
    doc["final_answer"] = {"text": final_text, "latex": final_latex}

    fence_plots, fence_errors = _parse_plotly_fences(raw_text, error_prefix="legacy_plotly")
    doc["plots"] = fence_plots
    doc["parse_errors"].extend(fence_errors)

    doc["parse_status"] = _to_parse_status(doc["steps"], final_text, final_latex)
    if doc["parse_status"] == "failed":
        return None
    return doc


def _parse_line_solution(raw_text: str, problem_text: str) -> Dict[str, Any]:
    text = raw_text or ""
    doc = _new_doc(problem_text, text)
    lines = text.splitlines()

    domain_constraints: List[str] = []
    verification: List[str] = []
    steps: List[Dict[str, Any]] = []
    plots: List[Dict[str, Any]] = []
    final_text = ""
    final_latex = ""

    in_domain = False
    in_verification = False
    current_step: Optional[Dict[str, Any]] = None

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()
        if not line:
            if current_step:
                current_step["body_lines"].append("")
            i += 1
            continue

        sentinel = _PLOT_SENTINEL_RE.match(line)
        if sentinel:
            payload, consumed = _extract_fenced_json_after(lines, i)
            if payload and _is_valid_plotly_payload(payload):
                plots.append({"id": sentinel.group(1), "plotly": payload})
            i = consumed + 1
            continue

        if line.lower().startswith("domain constraints:"):
            in_domain = True
            in_verification = False
            suffix = line.split(":", 1)[1].strip()
            if suffix:
                domain_constraints.append(_normalize_constraint_item(_BULLET_PREFIX_RE.sub("", suffix).strip()))
            i += 1
            continue

        if line.lower().startswith("verification:"):
            in_verification = True
            in_domain = False
            i += 1
            continue

        step_match = _STEP_HEADER_LOOSE_RE.match(line)
        if step_match:
            in_domain = False
            in_verification = False
            if current_step:
                current_step["body_markdown"] = "\n".join(current_step.pop("body_lines")).strip()
                steps.append(current_step)
            current_step = {
                "k": int(step_match.group(1)),
                "title": step_match.group(2).strip(),
                "body_lines": [],
            }
            i += 1
            continue

        final_answer_match = _FINAL_ANSWER_RE.match(line)
        if final_answer_match:
            final_text = final_answer_match.group(1).strip()
            i += 1
            continue
        final_text_match = _FINAL_TEXT_BOLD_RE.match(line) or _FINAL_TEXT_PLAIN_RE.match(line)
        if final_text_match:
            final_text = final_text_match.group(1).strip()
            i += 1
            continue

        final_latex_match = _FINAL_LATEX_RE.match(line)
        if final_latex_match:
            final_latex = _strip_math_delimiters(final_latex_match.group(1).strip())
            i += 1
            continue
        final_latex_bold_match = _FINAL_LATEX_BOLD_RE.match(line)
        if final_latex_bold_match:
            final_latex = _strip_math_delimiters(final_latex_bold_match.group(1).strip())
            i += 1
            continue

        if in_domain:
            cleaned = _normalize_constraint_item(_BULLET_PREFIX_RE.sub("", raw_line).strip())
            if cleaned:
                domain_constraints.append(cleaned)
        elif in_verification:
            cleaned = _BULLET_PREFIX_RE.sub("", raw_line).strip()
            if cleaned:
                verification.append(cleaned)
        elif current_step:
            current_step["body_lines"].append(raw_line.rstrip())

        i += 1

    if current_step:
        current_step["body_markdown"] = "\n".join(current_step.pop("body_lines")).strip()
        steps.append(current_step)

    fence_plots, fence_errors = _parse_plotly_fences(text, error_prefix="line_plotly")
    plots.extend(fence_plots)
    doc["parse_errors"].extend(fence_errors)
    doc["domain_constraints"] = _dedupe_preserve_order(domain_constraints)
    doc["steps"] = steps
    doc["plots"] = plots
    doc["verification"] = verification
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_text or ""):
        final_text = ""
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_latex or ""):
        final_latex = ""
    doc["final_answer"] = {"text": final_text, "latex": final_latex}
    doc["parse_status"] = _to_parse_status(steps, final_text, final_latex)
    return doc


def parse_solution_doc(text: str, problem_text: str = "") -> Dict[str, Any]:
    raw_text = text or ""
    normalized, normalization_report = latex_normalize_with_report(raw_text)

    candidates: List[Dict[str, Any]] = []

    markdown_doc = _parse_markdown_solution(normalized, problem_text)
    if markdown_doc:
        candidates.append(markdown_doc)

    json_doc = _parse_json_solution(normalized, problem_text)
    if json_doc:
        candidates.append(json_doc)

    legacy_doc = _parse_legacy_blob(normalized, problem_text)
    if legacy_doc:
        candidates.append(legacy_doc)

    line_doc = _parse_line_solution(normalized, problem_text)
    candidates.append(line_doc)

    selected = next((doc for doc in candidates if doc.get("parse_status") == "ok"), None)
    if selected is None:
        partial_with_signal = next(
            (
                doc
                for doc in candidates
                if doc.get("parse_status") == "partial" and _doc_has_meaningful_content(doc)
            ),
            None,
        )
        if partial_with_signal is not None:
            selected = partial_with_signal
    if selected is None:
        selected = next((doc for doc in candidates if doc.get("parse_status") == "partial"), None)
    if selected is None:
        selected = next((doc for doc in candidates if doc.get("parse_status") == "failed"), None)
    if selected is None:
        selected = _new_doc(problem_text, raw_text)

    existing_report = [str(item).strip() for item in (selected.get("latex_normalization_report") or []) if str(item).strip()]
    selected["latex_normalization_report"] = _dedupe_preserve_order(existing_report + normalization_report)
    selected["raw_output_markdown"] = raw_text
    selected["raw_fallback"] = raw_text
    if not selected.get("parse_status"):
        selected["parse_status"] = "failed"
    return selected


def render_solution_doc_markdown(solution_doc: Dict[str, Any]) -> str:
    doc = solution_doc or {}
    recognized = (doc.get("recognized_problem") or {}).get("text") or "N/A"
    domain_constraints = doc.get("domain_constraints") or []
    steps = doc.get("steps") or []
    plots = doc.get("plots") or []
    verification = doc.get("verification") or []
    final = doc.get("final_answer") or {}
    final_text = str(final.get("text") or "").strip()
    final_latex = _strip_math_delimiters(str(final.get("latex") or "").strip())
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_text or ""):
        final_text = ""
    if _FINAL_ANSWER_PLACEHOLDER_RE.match(final_latex or ""):
        final_latex = ""

    lines: List[str] = ["# Recognized Problem", recognized, ""]

    if domain_constraints:
        lines.append("# Domain Constraints")
        for item in domain_constraints:
            lines.append(f"- {item}")
        lines.append("")

    if steps:
        lines.append("# Steps")
        for idx, step in enumerate(steps, start=1):
            k = int(step.get("k") or idx)
            title = str(step.get("title") or f"Step {k}").strip()
            body = str(step.get("body_markdown") or "").strip()
            math_latex = (
                str(step.get("math_latex") or step.get("mathLatex") or step.get("math") or "").strip()
            )
            lines.append(f"## Step {k}: {title}")
            if body:
                lines.append(body)
            if math_latex:
                lines.append(f"$$\n{math_latex}\n$$")
            lines.append("")

    valid_plots = []
    for plot in plots:
        payload = plot.get("plotly")
        if isinstance(payload, dict) and _is_valid_plotly_payload(payload):
            valid_plots.append(payload)
    if valid_plots:
        lines.append("# Graphs")
        for payload in valid_plots:
            lines.append("```plotly")
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")

    if verification:
        lines.append("# Verification")
        for item in verification:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("# Final Answer")
    if final_text:
        lines.append(f"**Text:** {final_text}")
    if final_latex:
        lines.append(f"**LaTeX:** $${final_latex}$$")
    return "\n".join(lines).strip() + "\n"


def _latexish_to_sympy_expr(raw: str) -> str:
    expr = (raw or "").strip()
    expr = expr.replace("$$", "").replace("$", "")
    expr = expr.replace(r"\cdot", "*").replace(r"\times", "*")
    expr = expr.replace(r"\left", "").replace(r"\right", "")
    expr = expr.replace(r"\geq", ">=").replace(r"\leq", "<=").replace(r"\neq", "!=")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", expr)
    expr = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", expr)
    expr = re.sub(r"\\([a-zA-Z]+)", r"\1", expr)
    expr = expr.replace("{", "(").replace("}", ")")
    return expr.strip()


def _safe_parse_expr(expr: str):
    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
    return parse_expr(
        expr,
        transformations=transformations,
        local_dict={"sqrt": sqrt, "x": Symbol("x")},
        evaluate=True,
    )


def _parse_equation(problem_text: str) -> Tuple[Optional[Any], Optional[Any]]:
    text = latex_normalize(problem_text or "")
    line = ""
    for candidate in text.splitlines():
        if "=" in candidate:
            line = candidate.strip()
            break
    if not line and "=" in text:
        line = text.strip()
    if not line or "=" not in line:
        return None, None

    lhs_raw, rhs_raw = line.split("=", 1)
    try:
        lhs = _safe_parse_expr(_latexish_to_sympy_expr(lhs_raw))
        rhs = _safe_parse_expr(_latexish_to_sympy_expr(rhs_raw))
    except Exception:
        return None, None
    return lhs, rhs


def _contains_sqrt_like(expr: Any) -> bool:
    for node in preorder_traversal(expr):
        func = getattr(node, "func", None)
        func_name = getattr(func, "__name__", str(func))
        if func_name == "sqrt":
            return True
        if func_name == "Pow":
            args = getattr(node, "args", ())
            if len(args) == 2 and str(args[1]) in {"1/2", "0.5"}:
                return True
    return False


def _extract_domain_constraints(lhs: Any, rhs: Any, enforce_rhs_nonnegative: bool) -> List[str]:
    constraints: List[str] = []
    for expr in (lhs, rhs):
        for node in preorder_traversal(expr):
            func = getattr(node, "func", None)
            func_name = getattr(func, "__name__", str(func))
            if func_name == "sqrt" and len(getattr(node, "args", [])) == 1:
                constraints.append(f"${str(node.args[0])} \\ge 0$")
                continue
            if func_name == "Pow":
                args = getattr(node, "args", ())
                if len(args) == 2 and str(args[1]) in {"1/2", "0.5"}:
                    constraints.append(f"${str(args[0])} \\ge 0$")
                    continue
                if len(args) == 2:
                    exponent = args[1]
                    try:
                        if bool(getattr(exponent, "is_number", False)) and float(exponent) < 0:
                            constraints.append(f"${str(args[0])} \\ne 0$")
                    except Exception:
                        pass
            if func_name == "log" and len(getattr(node, "args", [])) >= 1:
                constraints.append(f"${str(node.args[0])} > 0$")
    if enforce_rhs_nonnegative:
        constraints.append(f"${str(rhs)} \\ge 0$")
    return _dedupe_preserve_order(constraints)


def _extract_candidate_numbers(text: str) -> List[S]:
    matches = re.findall(r"\bx\s*=\s*([-+]?\d+(?:\.\d+)?)", text or "", flags=re.IGNORECASE)
    out: List[S] = []
    for match in matches:
        try:
            out.append(S(match))
        except Exception:
            continue
    unique: List[S] = []
    for value in out:
        if value not in unique:
            unique.append(value)
    return unique


def _verify_candidate(lhs: Any, rhs: Any, candidate: S, enforce_rhs_nonnegative: bool) -> bool:
    x = Symbol("x")
    try:
        lhs_v = lhs.subs(x, candidate).evalf()
        rhs_v = rhs.subs(x, candidate).evalf()
        lhs_f = float(lhs_v)
        rhs_f = float(rhs_v)
    except Exception:
        return False

    if not math.isfinite(lhs_f) or not math.isfinite(rhs_f):
        return False
    if enforce_rhs_nonnegative and rhs_f < -1e-9:
        return False
    return abs(lhs_f - rhs_f) <= 1e-7


def _final_answer_from_values(values: List[S]) -> Dict[str, str]:
    if not values:
        return {"text": "No real solution", "latex": r"\varnothing"}
    ordered = sorted(values, key=lambda value: float(value))
    if len(ordered) == 1:
        value = ordered[0]
        return {"text": f"x = {value}", "latex": f"x = {value}"}
    joined = ", ".join(str(value) for value in ordered)
    return {"text": f"x in {{{joined}}}", "latex": f"x \\in \\{{{joined}\\}}"}


def _constraint_key(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip())


def apply_algebra_autocorrect(solution_doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(solution_doc or {})
    recognized = doc.get("recognized_problem") or {}
    problem_text = str(recognized.get("latex") or recognized.get("text") or "")
    if re.search(r"\b(inverse|function|domain|range)\b", problem_text, flags=re.IGNORECASE):
        return doc

    lhs, rhs = _parse_equation(problem_text)
    if lhs is None or rhs is None:
        return doc
    if "x" not in str(lhs) and "x" not in str(rhs):
        return doc

    enforce_rhs_nonnegative = _contains_sqrt_like(lhs)
    constraints = _extract_domain_constraints(lhs, rhs, enforce_rhs_nonnegative)
    current_constraints = list(doc.get("domain_constraints") or [])
    existing_constraint_keys = {_constraint_key(item) for item in current_constraints}
    for item in constraints:
        key = _constraint_key(item)
        if key not in existing_constraint_keys:
            current_constraints.append(item)
            existing_constraint_keys.add(key)
    doc["domain_constraints"] = current_constraints

    raw_fallback = str(doc.get("raw_fallback") or "")
    final = doc.get("final_answer") or {}
    typed_candidates: List[S] = []
    for source in (raw_fallback, str(final.get("text") or ""), str(final.get("latex") or "")):
        for candidate in _extract_candidate_numbers(source):
            if candidate not in typed_candidates:
                typed_candidates.append(candidate)

    if not typed_candidates:
        try:
            solved = solve(Eq(lhs, rhs), Symbol("x"))
            typed_candidates = [value for value in solved if getattr(value, "is_real", False)]
        except Exception:
            typed_candidates = []

    verified: List[S] = []
    for candidate in typed_candidates:
        if _verify_candidate(lhs, rhs, candidate, enforce_rhs_nonnegative):
            if candidate not in verified:
                verified.append(candidate)

    if not verified:
        return doc

    corrected = _final_answer_from_values(verified)
    before = str(final.get("latex") or final.get("text") or "").strip()
    after = str(corrected.get("latex") or corrected.get("text") or "").strip()

    if after and before != after:
        doc["final_answer"] = corrected
        doc["autocorrect"] = {
            "applied": True,
            "reason": "equation_substitution_verified",
            "before": before,
            "after": after,
        }
    else:
        doc["autocorrect"] = {"applied": False}
    return doc


def build_solution_doc(raw_text: str, problem_text: str) -> Dict[str, Any]:
    parsed = parse_solution_doc(raw_text, problem_text=problem_text)
    return apply_algebra_autocorrect(parsed)
