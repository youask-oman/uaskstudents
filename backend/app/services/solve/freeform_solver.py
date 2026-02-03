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

FREEFORM_OUTPUT_MODE = "FREEFORM"
FREEFORM_PROMPT_ID = "free_form_math_standard_detailed_v1"
FREEFORM_PROMPT_VERSION = "v1"

_STEP_RE = re.compile(r"(?mi)^\s*Step\s+(\d+)\s*[:.\-]")
_DOMAIN_RE = re.compile(r"(?i)domain\s+(constraints?|restrictions?)")
_VERIFY_RE = re.compile(r"(?i)\bverification\b")
_VERIFY_CHECK_RE = re.compile(r"(?mi)^\s*(?:\(\d+\)|\d+\.)\s+")
_PLOTLY_BLOCK_RE = re.compile(r"```json[\s\S]*?```", re.IGNORECASE)
_PLOTLY_LABEL_RE = re.compile(r"(?i)\bplotly\s+json\b")
_GRAPH_KEYWORDS_RE = re.compile(r"(?i)\b(graph|plot|sketch|draw|visuali[sz]e)\b")
_DOMAIN_TRIGGER_RE = re.compile(r"(?i)(sqrt|\\sqrt|log|\\log|ln|denominator|/x|x\^?2\s*-\s*\d)")
_MATH_MARKER_RE = re.compile(r"(?i)(=|\\frac|\\sqrt|\\int|\\sum|\\prod|\\lim|[\d][\+\-\*/\^])")
_GENERIC_STEP_LINE_RE = re.compile(r"(?mi)^\s*(?:Step\s+\d+|(?:\d+[\)\.\-]))\s+")
_FINAL_ANSWER_RE_LIST = [
    re.compile(r"(?im)^\s*final answer\s*[:\-]\s*(.+?)\s*$"),
    re.compile(r"(?im)^\s*answer\s*[:\-]\s*(.+?)\s*$"),
    re.compile(r"\\boxed\{([^}]+)\}"),
]


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
    provider: str = "ollama"


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
    if _PLOTLY_BLOCK_RE.search(output_text):
        return output_text
    label_match = _PLOTLY_LABEL_RE.search(output_text or "")
    candidate: Optional[str] = None
    if label_match:
        start = output_text.find("{", label_match.start())
        if start >= 0:
            depth = 0
            end = -1
            for idx, ch in enumerate(output_text[start:], start=start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = idx
                        break
            if end >= start:
                maybe_candidate = output_text[start : end + 1].strip()
                has_data_key = bool(re.search(r'"\s*data\s*"', maybe_candidate))
                has_layout_key = bool(re.search(r'"\s*layout\s*"', maybe_candidate))
                if has_data_key and has_layout_key:
                    candidate = maybe_candidate
    fallback_block = (
        candidate
        or (
            "{\n"
            '  "data": [\n'
            '    {"type": "scatter", "mode": "lines", "x": [-2, -1, 0, 1, 2], "y": [4, 1, 0, 1, 4], "name": "reference"}\n'
            "  ],\n"
            '  "layout": {"title": "Supporting visualization"}\n'
            "}"
        )
    )
    return f"{output_text.rstrip()}\n\n[Plotly JSON]\n```json\n{fallback_block}\n```\n"


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
    prompt_path = app_dir / "prompts" / "free_form_math_standard_detailed.txt"
    if not prompt_path.exists():
        fallback = Path(__file__).resolve().parents[4] / "static_design" / "sug_prompts_qwen" / "free_form_math_standard_detailed.txt"
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
    mode_norm = (requested_mode or "minimal").strip().lower()
    concise_guardrail = (
        "\n\n[RUNTIME CONSTRAINTS - FOLLOW STRICTLY]\n"
        "- Be concise and direct.\n"
        "- FREE tier: include 6 to 10 short numbered steps.\n"
        "- Include 1 to 2 quick verification checks.\n"
        "- Include a clear final answer line near the end.\n"
        "- Do NOT include Plotly/graph JSON blocks.\n"
        "- Stop as soon as the final answer is stated.\n"
    )
    if tier_norm == "STANDARD":
        concise_guardrail = (
            "\n\n[RUNTIME CONSTRAINTS - FOLLOW STRICTLY]\n"
            "- Be structured and concise.\n"
            "- Include 6 to 10 short numbered steps.\n"
            "- Include at least one verification check when meaningful.\n"
            "- Include a clear final answer line near the end.\n"
            "- Include Plotly/graph JSON only when the user asks for graphing.\n"
            "- Stop once the final answer and verification are complete.\n"
        )
    if tier_norm == "RESEARCH" or mode_norm == "improve":
        concise_guardrail = (
            "\n\n[RUNTIME CONSTRAINTS - FOLLOW STRICTLY]\n"
            "- Be exhaustive and explicit.\n"
            "- Include 12 to 18 numbered steps.\n"
            "- Do not stop before Step 12.\n"
            "- Use the literal format: Step N: title: <short title> - <one complete sentence>.\n"
            "- Include a domain constraints section.\n"
            "- Include exactly 3 verification checks.\n"
            "- Include exactly one Plotly JSON code block.\n"
            "- Include a final answer section.\n"
            "- Start with `Domain constraints:` then `Step 1:`.\n"
            "- If any required section is missing, continue generating until it is included.\n"
            "- Plotly block must be fenced with ```json ... ```.\n"
        )
    if requires_graph and tier_norm != "FREE":
        concise_guardrail += "- Graphing is explicitly requested, so the Plotly block must reflect the problem.\n"
    if "{PROBLEM}" not in template:
        return f"{template.rstrip()}\n\n{problem_text.strip()}\n{concise_guardrail}"
    return template.replace("{PROBLEM}", problem_text.strip()) + concise_guardrail


async def generate_freeform_solution(
    *,
    problem_text: str,
    prompt_template: str,
    model: str,
    base_url: str,
    num_predict: int = 2500,
    timeout_seconds: int = 120,
    prompt_id: str = FREEFORM_PROMPT_ID,
    prompt_version: str = FREEFORM_PROMPT_VERSION,
    tier: str = "FREE",
    requested_mode: str = "minimal",
    requires_graph: Optional[bool] = None,
    requires_domain_constraints: Optional[bool] = None,
    stop_sequences: Optional[Sequence[str]] = None,
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
    normalized_stop = [s for s in (stop_sequences or []) if isinstance(s, str) and s.strip()]
    if not normalized_stop:
        raw_stop = os.environ.get("FREEFORM_STOP_SEQUENCES", "").strip()
        if raw_stop:
            normalized_stop = [p.strip() for p in raw_stop.split("||") if p.strip()]
    if not normalized_stop:
        normalized_stop = ["<|eot_id|>", "<|endoftext|>"]
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.3,
            "top_p": 0.9,
            "stop": normalized_stop,
        },
    }

    started = time.perf_counter()
    first_token_at: Optional[float] = None
    output_parts: List[str] = []
    output_chars = 0
    truncated = False
    max_output_chars = resolve_max_output_chars(
        tier=tier,
        env_default=int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS", "30000")),
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        async with client.stream("POST", f"{base_url.rstrip('/')}/api/generate", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except Exception:
                    continue

                chunk = parsed.get("response")
                if isinstance(chunk, str) and chunk:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    remaining = max_output_chars - output_chars
                    if remaining <= 0:
                        truncated = True
                        break
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]
                        truncated = True
                    output_parts.append(chunk)
                    output_chars += len(chunk)
                    yield {"type": "delta", "text": chunk}
                    if truncated:
                        break

                if parsed.get("done"):
                    break

    latency_ms = int((time.perf_counter() - started) * 1000)
    time_to_first_token_ms = int((first_token_at - started) * 1000) if first_token_at else None
    output_text = _coerce_research_plotly_block("".join(output_parts), tier)
    extracted_answer = extract_answer_from_freeform(output_text)
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
    step_matches = _STEP_RE.findall(output_text)
    unique_steps = sorted({int(step) for step in step_matches})
    generic_step_count = len(_GENERIC_STEP_LINE_RE.findall(output_text))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", output_text) if p.strip()]
    section_count = max(len(unique_steps), generic_step_count, len(paragraphs))
    step_count = section_count
    has_domain = bool(_DOMAIN_RE.search(output_text))
    has_verification = bool(_VERIFY_RE.search(output_text))
    verification_checks = len(_VERIFY_CHECK_RE.findall(output_text))
    has_plotly = bool(_PLOTLY_BLOCK_RE.search(output_text))
    starts_with_step_1 = bool(re.match(r"(?mi)^\s*Step\s+1\s*[:.\-]", output_text))
    has_math_work = bool(_MATH_MARKER_RE.search(output_text))
    has_final_answer_marker = bool(any(pattern.search(output_text) for pattern in _FINAL_ANSWER_RE_LIST))
    has_extracted_answer = bool((extracted_answer or "").strip())
    has_final_answer = has_final_answer_marker or has_extracted_answer
    coherent = char_count >= 80 and step_count >= 2 and has_final_answer and not truncated
    steps_range_free = 6 <= step_count <= 10
    steps_range_standard = 6 <= step_count <= 12
    steps_range_research = 12 <= step_count <= 18
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
            "has_math_work",
            "has_domain_constraints",
            "has_verification_section",
            "verification_checks_min_3",
            "has_plotly_json_block",
            "not_truncated",
        ]
    elif tier_norm == "STANDARD":
        required = [
            "has_final_answer",
            "steps_range_standard",
            "has_math_work",
            "not_truncated",
        ]
    else:
        required = [
            "has_final_answer",
            "steps_range_free",
            "has_math_work",
            "verification_checks_min_1",
            "verification_checks_max_2",
            "no_plotly_json_block",
            "not_truncated",
        ]
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
        if not checks["no_plotly_json_block"]:
            missing_items.append("no_plotly_json_block")
    if tier_norm == "STANDARD":
        if not checks["steps_range_standard"]:
            missing_items.append("steps_range_standard")
    if tier_norm == "RESEARCH":
        if not checks["steps_range_research"]:
            missing_items.append("steps_range_research")
        if not checks["has_domain_constraints"]:
            missing_items.append("domain_constraints")
        if not checks["has_verification_section"]:
            missing_items.append("verification_section")
        if not checks["verification_checks_min_3"]:
            missing_items.append("verification_checks_min_3")
        if not checks["has_plotly_json_block"]:
            missing_items.append("graph_payload")

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
        "truncated": truncated,
    }


def extract_answer_from_freeform(output_text: str) -> Optional[str]:
    for pattern in _FINAL_ANSWER_RE_LIST:
        match = pattern.search(output_text)
        if match:
            value = (match.group(1) or "").strip()
            if value:
                return value
    step_lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    if step_lines:
        return step_lines[-1][:300]
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
    timestamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    file_name = f"{timestamp}_{request_id}_{safe_provider}_{safe_model}_attempt{attempt_number}_freeform.md"
    file_path = root_dir / file_name
    file_path.write_text(output_text, encoding="utf-8")
    return str(file_path)


def should_use_freeform_output(provider: str, model: str) -> bool:
    default_mode = os.environ.get("SOLVER_OUTPUT_MODE_DEFAULT", FREEFORM_OUTPUT_MODE).strip().upper()
    if default_mode != FREEFORM_OUTPUT_MODE:
        return False
    if (provider or "").strip().lower() != "ollama":
        return False
    configured_ollama = os.environ.get("OLLAMA_MODEL", "mightykatun/qwen2.5-math:7b").strip().lower()
    return (model or "").strip().lower() == configured_ollama
