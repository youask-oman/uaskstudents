from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

import httpx
from app.services.solve.solution_doc import build_solution_doc, latex_normalize, render_solution_doc_markdown

FREEFORM_OUTPUT_MODE = "FREEFORM"
FREEFORM_PROMPT_ID = "free_form_math_standard_detailed_v1"
FREEFORM_PROMPT_VERSION = "v1"

_STEP_RE_STRICT = re.compile(r"(?mi)^\s*##\s*Step\s+(\d+)\s*:\s+.+$")
_STEP_RE_LOOSE = re.compile(r"(?mi)^\s*(?:##\s*)?(?:[-*]\s*)?(?:\*{1,2}\s*)?Step\s+(\d+)\s*[:.\-]")
_DOMAIN_RE = re.compile(r"(?i)domain\s+(constraints?|restrictions?)")
_VERIFY_RE = re.compile(r"(?i)\bverification\b")
_VERIFY_CHECK_RE = re.compile(
    r"(?mi)^\s*(?:[-*]\s*)?(?:\*{1,2}\s*)?(?:\(\d+\)|\d+[.)]|verification\s+check\s+\d+)\s*(?:[:.\-])?\s+"
)
_PLOTLY_BLOCK_RE = re.compile(r"```(?:plotly|json)[\s\S]*?```", re.IGNORECASE)
_PLOTLY_LABEL_RE = re.compile(r"(?i)\bplotly\s+json\b")
_GRAPH_KEYWORDS_RE = re.compile(r"(?i)\b(graph|plot|sketch|draw|visuali[sz]e)\b")
_DOMAIN_TRIGGER_RE = re.compile(r"(?i)(sqrt|\\sqrt|log|\\log|ln|denominator|/x|x\^?2\s*-\s*\d)")
_MATH_MARKER_RE = re.compile(r"(?i)(=|\\frac|\\sqrt|\\int|\\sum|\\prod|\\lim|[\d][\+\-\*/\^])")
_GENERIC_STEP_LINE_RE = re.compile(r"(?mi)^\s*(?:(?:##\s*)?Step\s+\d+|(?:\d+[\)\.\-]))\s+")
_FINAL_ANSWER_RE_LIST = [
    re.compile(r"(?im)^[ \t]*final answer[ \t]*[:\-][ \t]*(.+?)[ \t]*$"),
    re.compile(r"(?im)^[ \t]*answer[ \t]*[:\-][ \t]*(.+?)[ \t]*$"),
    re.compile(r"(?im)^[ \t]*\*\*text:\*\*[ \t]*(.+?)[ \t]*$"),
    re.compile(r"\\boxed\{([^}]+)\}"),
]
_FINAL_ANSWER_HEADER_RE = re.compile(r"(?im)^\s*\*{0,2}\s*final answer\s*\*{0,2}\s*:?\s*$")
_DISPLAY_BLOCK_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_EQUATION_LINE_RE = re.compile(r"(?m)^\s*([^\n]{1,260}[=<>][^\n]{1,260})\s*$")
_PLACEHOLDER_ANSWER_RE = re.compile(r"^(?:n/?a|none|null|not\s+provided|unknown|-+)$", re.IGNORECASE)


@dataclass
class FreeformAttemptResult:
    output_text: str
    latency_ms: int
    time_to_first_token_ms: Optional[int]
    truncated: bool
    validation: Dict[str, Any]
    extracted_answer: Optional[str]
    prompt_id: str = FREEFORM_PROMPT_ID
    prompt_version: str = FREEFORM_PROMPT_VERSION
    provider: str = "openai"
    solution_doc: Optional[Dict[str, Any]] = None


def _normalize_tier(value: Optional[str]) -> str:
    tier = (value or "FREE").strip().upper()
    if tier not in {"FREE", "STANDARD", "RESEARCH"}:
        return "FREE"
    return tier


def _problem_requires_graph(problem_text: str) -> bool:
    return bool(_GRAPH_KEYWORDS_RE.search(problem_text or ""))


def _problem_requires_domain_constraints(problem_text: str) -> bool:
    return bool(_DOMAIN_TRIGGER_RE.search(problem_text or ""))


def _coerce_research_plotly_block(output_text: str, tier: str) -> str:
    if _normalize_tier(tier) != "RESEARCH":
        return output_text
    # Never inject random labels or fallback plot blocks.
    # If model emitted "[Plotly JSON]" with a fenced json block, normalize to fenced plotly only.
    normalized = re.sub(r"(?im)^\s*\[plotly json\]\s*$", "", output_text or "")
    normalized = re.sub(r"```json", "```plotly", normalized, flags=re.IGNORECASE)
    return normalized


def _normalize_to_markdown_contract(raw_text: str, problem_text: str) -> str:
    doc = build_solution_doc(raw_text or "", problem_text or "")
    parse_status = str(doc.get("parse_status") or "").strip().lower()
    has_structured_signal = bool(
        (doc.get("steps") or [])
        or (doc.get("plots") or [])
        or (doc.get("domain_constraints") or [])
        or (doc.get("verification") or [])
        or str((doc.get("final_answer") or {}).get("text") or "").strip()
        or str((doc.get("final_answer") or {}).get("latex") or "").strip()
    )
    # Keep raw output only when parsing failed or when partial parse has no useful structured signal.
    if parse_status == "failed" or (parse_status == "partial" and not has_structured_signal):
        raw = latex_normalize(raw_text or "").strip()
        if raw:
            return raw + ("\n" if not raw.endswith("\n") else "")
    return render_solution_doc_markdown(doc)


def resolve_num_predict(
    *,
    tier: str,
    difficulty: Optional[str],
    requested_mode: Optional[str],
    env_default: int,
) -> int:
    tier_norm = _normalize_tier(tier)
    diff = (difficulty or "").strip().lower()
    mode = (requested_mode or "").strip().lower()

    easy = int(os.environ.get("FREEFORM_NUM_PREDICT_EASY", "280"))
    medium = int(os.environ.get("FREEFORM_NUM_PREDICT_MEDIUM", "380"))
    hard = int(os.environ.get("FREEFORM_NUM_PREDICT_HARD", "700"))

    if tier_norm == "RESEARCH":
        research_floor = int(os.environ.get("FREEFORM_NUM_PREDICT_RESEARCH_FLOOR", "1400"))
        target = max(hard, research_floor)
    elif diff in {"easy", "intro", "simple"}:
        target = easy
    elif diff in {"hard", "advanced", "challenge"}:
        target = hard
    else:
        target = medium

    if mode in {"minimal", "concise"}:
        target = int(target * 0.75)
    if mode == "detailed":
        target = int(target * 1.15)
    if tier_norm == "FREE":
        target = min(target, int(os.environ.get("FREEFORM_NUM_PREDICT_FREE_CAP", "450")))
    elif tier_norm == "STANDARD" and mode in {"minimal", "concise"}:
        target = min(target, int(os.environ.get("FREEFORM_NUM_PREDICT_STANDARD_CAP", "650")))
    max_allowed = int(os.environ.get("FREEFORM_NUM_PREDICT_MAX", str(env_default)))
    return max(256, min(max(max_allowed, 256), target))


def resolve_timeout_seconds(*, tier: str, env_default: int) -> int:
    tier_norm = _normalize_tier(tier)
    if tier_norm == "RESEARCH":
        target = int(os.environ.get("FREEFORM_TIMEOUT_SECONDS_RESEARCH", "120"))
    elif tier_norm == "STANDARD":
        target = int(os.environ.get("FREEFORM_TIMEOUT_SECONDS_STANDARD", "60"))
    else:
        target = int(os.environ.get("FREEFORM_TIMEOUT_SECONDS_FREE", "35"))
    return max(15, min(max(env_default, 15), target))


def resolve_max_output_chars(*, tier: str, env_default: int) -> int:
    tier_norm = _normalize_tier(tier)
    if tier_norm == "RESEARCH":
        target = int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS_RESEARCH", "12000"))
    elif tier_norm == "STANDARD":
        target = int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS_STANDARD", "7000"))
    else:
        target = int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS_FREE", "4500"))
    return max(800, min(max(env_default, 800), target))


def load_default_freeform_prompt_template() -> str:
    app_dir = Path(__file__).resolve().parents[2]
    prompt_path = Path(__file__).resolve().parents[4] / "static_design" / "sug_prompts_openai" / "free_form_math_standard_detailed.txt"
    if not prompt_path.exists():
        fallback = app_dir / "prompts" / "free_form_math_standard_detailed.txt"
        if fallback.exists():
            prompt_path = fallback
    if not prompt_path.exists():
        raise FileNotFoundError(f"Missing free-form prompt template: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_freeform_prompt(
    problem_text: str,
    template: str,
    *,
    tier: str = "FREE",
    requested_mode: str = "minimal",
    requires_graph: bool = False,
) -> str:
    tier_norm = _normalize_tier(tier)
    if tier_norm == "RESEARCH":
        step_range = "12 to 18"
        verification_rule = "Include exactly 3 verification bullet checks."
    elif tier_norm == "STANDARD":
        step_range = "6 to 10"
        verification_rule = "Include 1 to 3 verification bullet checks."
    else:
        step_range = "6 to 10"
        verification_rule = "Include 1 to 2 verification bullet checks."

    plot_rule = (
        "- In # Graphs, include one or more fenced ```plotly blocks with valid Plotly JSON only when graphing is explicitly requested.\n"
        if requires_graph
        else "- In # Graphs, output exactly '- None'. Do not include Plotly JSON unless graphing is explicitly requested.\n"
    )

    concise_guardrail = (
        "\n\n[RUNTIME CONSTRAINTS - FOLLOW STRICTLY]\n"
        "- Output MUST be MARKDOWN only.\n"
        "- Use these exact section headers in order:\n"
        "  # Recognized Problem\n"
        "  # Domain Constraints\n"
        "  # Steps\n"
        "  # Graphs\n"
        "  # Verification\n"
        "  # Final Answer\n"
        "- In # Steps, each step must start with: ## Step k: Title\n"
        "- Step title must be 3-9 words, verb-first, Title Case.\n"
        "- Step body is multiline markdown until the next step header.\n"
        f"- Include {step_range} steps.\n"
        f"- {verification_rule}\n"
        "- In # Final Answer, output exactly:\n"
        "  **Text:** ...\n"
        "  **LaTeX:** $$...$$\n"
        "- Use only standard LaTeX delimiters: inline $...$ and display $$...$$.\n"
        "- Never output \\( \\) or \\[ \\].\n"
        "- Do NOT output a JSON object wrapper.\n"
        "- Do NOT output raw schema keys like \"steps\": [...].\n"
        "- Do NOT output '[Plotly JSON]' labels.\n"
        + plot_rule
    )
    if "{PROBLEM}" not in template:
        return f"{template.rstrip()}\n\n{problem_text.strip()}\n{concise_guardrail}"
    return template.replace("{PROBLEM}", problem_text.strip()) + concise_guardrail


async def generate_freeform_solution(
    *,
    problem_text: str,
    prompt_template: str,
    model: str,
    num_predict: int = 2500,
    timeout_seconds: int = 120,
    prompt_id: str = FREEFORM_PROMPT_ID,
    prompt_version: str = FREEFORM_PROMPT_VERSION,
    tier: str = "FREE",
    requested_mode: str = "minimal",
    requires_graph: Optional[bool] = None,
    requires_domain_constraints: Optional[bool] = None,
    stop_sequences: Optional[Sequence[str]] = None,
    system_prompt: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    if requires_graph is None:
        requires_graph = _problem_requires_graph(problem_text)
    if requires_domain_constraints is None:
        requires_domain_constraints = _problem_requires_domain_constraints(problem_text)
    prompt = build_freeform_prompt(
        problem_text,
        prompt_template,
        tier=tier,
        requested_mode=requested_mode,
        requires_graph=bool(requires_graph),
    )
    started = time.perf_counter()
    first_token_at: Optional[float] = None
    output_text = ""
    truncated = False
    max_output_chars = resolve_max_output_chars(
        tier=tier,
        env_default=int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS", "30000")),
    )
    from app.services.llm import get_llm_manager

    client = get_llm_manager().get_client("openai")
    resolved_system_prompt = (
        (system_prompt or "").strip()
        or (os.environ.get("FREEFORM_SYSTEM_PROMPT") or "").strip()
        or ""
    )
    messages_payload = [{"role": "user", "content": prompt}]
    if resolved_system_prompt:
        messages_payload.insert(0, {"role": "system", "content": resolved_system_prompt})
    response = await client.generate(
        messages=messages_payload,
        system_prompt=None,
        prompt=None,
        json_schema=None,
        max_tokens=max(256, num_predict),
        temperature=None,
        stream=False,
        request_id=None,
        model=model,
        verbosity="high" if (requested_mode or "").lower() in {"detailed", "improve"} else "low",
    )
    raw_text = response.content or ""
    if first_token_at is None and raw_text:
        first_token_at = time.perf_counter()
    normalized_output = _normalize_to_markdown_contract(raw_text, problem_text)
    if len(normalized_output) > max_output_chars:
        output_text = normalized_output[:max_output_chars]
        truncated = True
    else:
        output_text = normalized_output

    chunk_size = 512
    for idx in range(0, len(output_text), chunk_size):
        yield {"type": "delta", "text": output_text[idx : idx + chunk_size]}

    latency_ms = int((time.perf_counter() - started) * 1000)
    time_to_first_token_ms = int((first_token_at - started) * 1000) if first_token_at else None
    output_text = _coerce_research_plotly_block(output_text, tier)
    solution_doc = build_solution_doc(output_text, problem_text)
    extracted_answer = extract_answer_from_freeform(output_text)
    if not extracted_answer:
        extracted_answer = (
            (solution_doc.get("final_answer") or {}).get("latex")
            or (solution_doc.get("final_answer") or {}).get("text")
            or ""
        )
    validation = validate_freeform_output(
        output_text,
        tier=tier,
        requested_mode=requested_mode,
        requires_graph=bool(requires_graph),
        requires_domain_constraints=bool(requires_domain_constraints),
        extracted_answer=extracted_answer,
        truncated=truncated,
    )

    yield {
        "type": "result",
        "result": FreeformAttemptResult(
            output_text=output_text,
            latency_ms=latency_ms,
            time_to_first_token_ms=time_to_first_token_ms,
            truncated=truncated,
            validation=validation,
            extracted_answer=extracted_answer,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            solution_doc=solution_doc,
        ),
    }


def validate_freeform_output(
    output_text: str,
    *,
    tier: str = "FREE",
    requested_mode: str = "minimal",
    requires_graph: bool = False,
    requires_domain_constraints: bool = False,
    extracted_answer: Optional[str] = None,
    truncated: bool = False,
) -> Dict[str, Any]:
    char_count = len(output_text)
    strict_step_matches = _STEP_RE_STRICT.findall(output_text)
    loose_step_matches = _STEP_RE_LOOSE.findall(output_text)
    step_matches = strict_step_matches or loose_step_matches
    unique_steps = sorted({int(step) for step in step_matches})
    explicit_step_count = len(unique_steps)
    generic_step_count = len(_GENERIC_STEP_LINE_RE.findall(output_text))
    step_count = explicit_step_count if explicit_step_count > 0 else generic_step_count
    has_domain = bool(_DOMAIN_RE.search(output_text))
    has_verification = bool(_VERIFY_RE.search(output_text))
    verification_checks = len(_VERIFY_CHECK_RE.findall(output_text))
    has_plotly = bool(_PLOTLY_BLOCK_RE.search(output_text))
    starts_with_step_1 = bool(re.match(r"(?mi)^\s*(?:##\s*)?Step\s+1\s*[:.\-]", output_text))
    has_math_work = bool(_MATH_MARKER_RE.search(output_text))
    extracted_answer_value = (extracted_answer or "").strip()
    has_extracted_answer = bool(extracted_answer_value) and not bool(_PLACEHOLDER_ANSWER_RE.match(extracted_answer_value))
    has_final_answer_marker = bool(any(pattern.search(output_text) for pattern in _FINAL_ANSWER_RE_LIST))
    has_placeholder_final = bool(
        re.search(r"(?im)^\s*(?:\*\*text:\*\*|final\s*answer\s*:)\s*(?:n/?a|none|null|not\s+provided)\s*$", output_text)
    )
    has_final_answer = (has_final_answer_marker or has_extracted_answer) and not has_placeholder_final
    coherent = char_count >= 80 and step_count >= 2 and has_final_answer and not truncated
    steps_range_free = 6 <= step_count <= 10
    steps_range_standard = 6 <= step_count <= 10
    steps_range_research = 12 <= explicit_step_count <= 18
    verification_checks_min_1 = verification_checks >= 1
    verification_checks_max_2 = verification_checks <= 2
    verification_checks_min_3 = verification_checks >= 3
    no_plotly_block = not has_plotly

    base_checks = {
        "coherent": coherent,
        "has_final_answer": has_final_answer,
        "steps_min_2": step_count >= 2,
        "steps_min_3": step_count >= 3,
        "steps_min_4": step_count >= 4,
        "steps_min_6": step_count >= 6,
        "steps_min_8": step_count >= 8,
        "steps_min_10": step_count >= 10,
        "steps_range_free": steps_range_free,
        "steps_range_standard": steps_range_standard,
        "steps_range_research": steps_range_research,
        "research_explicit_steps_min_12": explicit_step_count >= 12,
        "has_math_work": has_math_work,
        "has_domain_constraints": has_domain,
        "has_verification_section": has_verification,
        "verification_checks_min_1": verification_checks_min_1,
        "verification_checks_max_2": verification_checks_max_2,
        "verification_checks_min_3": verification_checks_min_3,
        "has_plotly_json_block": has_plotly,
        "no_plotly_json_block": no_plotly_block,
        "has_domain_constraints_if_required": (not requires_domain_constraints) or has_domain,
        "has_graph_payload_if_required": (not requires_graph) or has_plotly,
        "not_truncated": not truncated,
    }
    legacy_checks = {
        "char_count_min_1800": char_count >= 1800,
        "char_count_target_max_2500": char_count <= 2500,
        "steps_min_12": step_count >= 12,
        "starts_with_step_1": starts_with_step_1,
    }
    checks = {**base_checks, **legacy_checks}

    tier_norm = _normalize_tier(tier)
    mode_norm = (requested_mode or "minimal").strip().lower()
    if tier_norm == "RESEARCH":
        required = [
            "has_final_answer",
            "steps_range_research",
            "research_explicit_steps_min_12",
            "has_math_work",
            "has_domain_constraints",
            "has_verification_section",
            "verification_checks_min_3",
            "not_truncated",
        ]
        required.append("has_graph_payload_if_required" if requires_graph else "no_plotly_json_block")
    elif tier_norm == "STANDARD":
        required = [
            "has_final_answer",
            "steps_range_standard",
            "has_math_work",
            "not_truncated",
        ]
        required.append("has_graph_payload_if_required" if requires_graph else "no_plotly_json_block")
    else:
        required = [
            "has_final_answer",
            "steps_range_free",
            "has_math_work",
            "verification_checks_min_1",
            "verification_checks_max_2",
            "not_truncated",
        ]
        required.append("has_graph_payload_if_required" if requires_graph else "no_plotly_json_block")
    failed_checks = [name for name in required if not checks.get(name, False)]
    passed_count = len(required) - len(failed_checks)
    quality_parts = [
        checks["coherent"],
        checks["has_final_answer"],
        checks["steps_min_2"],
        checks["steps_min_3"],
        checks["steps_min_4"],
        checks["steps_range_free"],
        checks["steps_range_standard"],
        checks["steps_range_research"],
        checks["research_explicit_steps_min_12"],
        checks["steps_min_10"],
        checks["has_math_work"],
        checks["has_domain_constraints"],
        checks["has_verification_section"],
        checks["verification_checks_min_1"],
        checks["verification_checks_max_2"],
        checks["verification_checks_min_3"],
        checks["has_plotly_json_block"],
        checks["no_plotly_json_block"],
        checks["not_truncated"],
    ]
    quality_score = int(round((sum(1 for ok in quality_parts if ok) / len(quality_parts)) * 100))
    missing_items: List[str] = []
    if not checks["has_final_answer"]:
        missing_items.append("final_answer")
    if tier_norm == "FREE" and not checks["steps_range_free"]:
        missing_items.append("steps_range_free")
    if not checks["has_math_work"]:
        missing_items.append("math_work")
    if tier_norm == "FREE":
        if not checks["verification_checks_min_1"]:
            missing_items.append("verification_checks_min_1")
        if not checks["verification_checks_max_2"]:
            missing_items.append("verification_checks_max_2")
        if requires_graph and not checks["has_graph_payload_if_required"]:
            missing_items.append("graph_payload")
        if not requires_graph and not checks["no_plotly_json_block"]:
            missing_items.append("no_plotly_json_block")
    if tier_norm == "STANDARD":
        if not checks["steps_range_standard"]:
            missing_items.append("steps_range_standard")
        if requires_graph and not checks["has_graph_payload_if_required"]:
            missing_items.append("graph_payload")
        if not requires_graph and not checks["no_plotly_json_block"]:
            missing_items.append("no_plotly_json_block")
    if tier_norm == "RESEARCH":
        if not checks["steps_range_research"]:
            missing_items.append("steps_range_research")
        if not checks["research_explicit_steps_min_12"]:
            missing_items.append("research_explicit_steps_min_12")
        if not checks["has_domain_constraints"]:
            missing_items.append("domain_constraints")
        if not checks["has_verification_section"]:
            missing_items.append("verification_section")
        if not checks["verification_checks_min_3"]:
            missing_items.append("verification_checks_min_3")
        if requires_graph and not checks["has_graph_payload_if_required"]:
            missing_items.append("graph_payload")
        if not requires_graph and not checks["no_plotly_json_block"]:
            missing_items.append("no_plotly_json_block")

    return {
        "is_valid": len(failed_checks) == 0,
        "is_usable": checks["coherent"],
        "score": f"{passed_count}/{len(required)}",
        "quality_score": quality_score,
        "policy_tier": tier_norm,
        "requested_mode": mode_norm,
        "requires_graph": requires_graph,
        "requires_domain_constraints": requires_domain_constraints,
        "checks": checks,
        "failed_checks": failed_checks,
        "missing_items": missing_items,
        "char_count": char_count,
        "step_count": step_count,
        "explicit_step_count": explicit_step_count,
        "truncated": truncated,
    }


def extract_answer_from_freeform(output_text: str) -> Optional[str]:
    def _clean_candidate(raw: Optional[str]) -> Optional[str]:
        value = (raw or "").strip()
        if not value:
            return None
        value = re.sub(r"^\*{1,3}\s*", "", value)
        value = re.sub(r"\s*\*{1,3}$", "", value).strip()
        value = re.sub(r"^\(?\d+\)?[.)]\s*", "", value).strip()
        value = re.sub(r"\s{2,}", " ", value)
        if not value:
            return None
        if re.match(r"(?i)^(step|verification|domain|check|plotly)\b", value):
            return None
        if re.match(r"(?i)^sub(?:stitution)?\.?$", value):
            return None
        return value[:320]

    for pattern in _FINAL_ANSWER_RE_LIST:
        match = pattern.search(output_text)
        if match:
            candidate = _clean_candidate(match.group(1) if match.lastindex else match.group(0))
            if candidate:
                return candidate

    lines = [line.rstrip() for line in output_text.splitlines()]
    for idx, line in enumerate(lines):
        if not _FINAL_ANSWER_HEADER_RE.match(line):
            continue
        for follow in lines[idx + 1 : idx + 9]:
            if not follow.strip():
                continue
            boxed = re.search(r"\\boxed\{([^}]+)\}", follow)
            if boxed:
                candidate = _clean_candidate(boxed.group(1))
                if candidate:
                    return candidate
            candidate = _clean_candidate(follow)
            if candidate and any(token in candidate for token in ("=", "\\frac", "\\sqrt", "\\pi", "\\theta")):
                return candidate

    display_blocks = _DISPLAY_BLOCK_RE.findall(output_text)
    for block in reversed(display_blocks):
        candidate = _clean_candidate(block.strip())
        if candidate and any(token in candidate for token in ("=", "\\boxed", "\\frac", "\\sqrt", "\\pi")):
            return candidate

    equation_lines = _EQUATION_LINE_RE.findall(output_text or "")
    for equation in reversed(equation_lines):
        candidate = _clean_candidate(equation)
        if candidate:
            return candidate

    step_lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    for line in reversed(step_lines):
        candidate = _clean_candidate(line)
        if candidate:
            return candidate
    return None


def archive_freeform_output(
    *,
    request_id: str,
    provider: str,
    model: str,
    attempt_number: int,
    output_text: str,
) -> str:
    now = datetime.utcnow()
    root_dir = Path(__file__).resolve().parents[4] / "storage" / "solver_outputs" / "freeform" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
    root_dir.mkdir(parents=True, exist_ok=True)
    safe_provider = re.sub(r"[^A-Za-z0-9._-]+", "-", provider or "unknown")
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", model or "unknown")
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    #file_name = f"{timestamp}_{request_id}_{safe_provider}_{safe_model}_attempt{attempt_number}_freeform.md"
    file_name = f"{timestamp}_{request_id}_uask_{attempt_number}_freeform.md"

    file_path = root_dir / file_name
    file_path.write_text(output_text, encoding="utf-8")
    return str(file_path)


def should_use_freeform_output(provider: str, model: str) -> bool:
    # Temporarily disabled - using JSON schema mode only
    return False
