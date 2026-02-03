from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

FREEFORM_OUTPUT_MODE = "FREEFORM"
FREEFORM_PROMPT_ID = "free_form_math_standard_detailed_v1"
FREEFORM_PROMPT_VERSION = "v1"

_STEP_RE = re.compile(r"(?mi)^\s*Step\s+(\d+)\s*[:.\-]")
_DOMAIN_RE = re.compile(r"(?i)domain\s+(constraints?|restrictions?)")
_VERIFY_RE = re.compile(r"(?i)\bverification\b")
_VERIFY_CHECK_RE = re.compile(r"(?mi)^\s*(?:\(\d+\)|\d+\.)\s+")
_PLOTLY_BLOCK_RE = re.compile(r"```json[\s\S]*?```", re.IGNORECASE)
_FINAL_ANSWER_RE_LIST = [
    re.compile(r"(?im)^\s*final answer\s*[:\-]\s*(.+?)\s*$"),
    re.compile(r"(?im)^\s*answer\s*[:\-]\s*(.+?)\s*$"),
    re.compile(r"\\boxed\{([^}]+)\}"),
]


@dataclass
class FreeformAttemptResult:
    output_text: str
    latency_ms: int
    validation: Dict[str, Any]
    extracted_answer: Optional[str]
    prompt_id: str = FREEFORM_PROMPT_ID
    prompt_version: str = FREEFORM_PROMPT_VERSION
    provider: str = "ollama"


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


def build_freeform_prompt(problem_text: str, template: str) -> str:
    if "{PROBLEM}" not in template:
        return f"{template.rstrip()}\n\n{problem_text.strip()}\n"
    return template.replace("{PROBLEM}", problem_text.strip())


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
) -> FreeformAttemptResult:
    prompt = build_freeform_prompt(problem_text, prompt_template)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.3,
            "top_p": 0.9,
            "stop": [],
        },
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = await client.post(f"{base_url.rstrip('/')}/api/generate", json=payload)
        response.raise_for_status()
        parsed = response.json()
    latency_ms = int((time.perf_counter() - started) * 1000)
    output_text = parsed.get("response", "")
    if not isinstance(output_text, str):
        output_text = str(output_text)
    validation = validate_freeform_output(output_text)
    extracted_answer = extract_answer_from_freeform(output_text)
    return FreeformAttemptResult(
        output_text=output_text,
        latency_ms=latency_ms,
        validation=validation,
        extracted_answer=extracted_answer,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
    )


def validate_freeform_output(output_text: str) -> Dict[str, Any]:
    char_count = len(output_text)
    step_matches = _STEP_RE.findall(output_text)
    unique_steps = sorted({int(step) for step in step_matches})
    step_count = len(unique_steps)
    has_domain = bool(_DOMAIN_RE.search(output_text))
    has_verification = bool(_VERIFY_RE.search(output_text))
    verification_checks = len(_VERIFY_CHECK_RE.findall(output_text))
    has_plotly = bool(_PLOTLY_BLOCK_RE.search(output_text))
    starts_with_step_1 = bool(re.match(r"(?mi)^\s*Step\s+1\s*[:.\-]", output_text))

    checks = {
        "char_count_min_1800": char_count >= 1800,
        "char_count_target_max_2500": char_count <= 2500,
        "steps_min_12": step_count >= 12,
        "starts_with_step_1": starts_with_step_1,
        "has_domain_constraints": has_domain,
        "has_verification_section": has_verification,
        "verification_checks_min_3": verification_checks >= 3,
        "has_plotly_json_block": has_plotly,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    passed_count = len(checks) - len(failed_checks)

    return {
        "is_valid": checks["char_count_min_1800"] and checks["steps_min_12"] and checks["has_domain_constraints"] and checks["has_verification_section"] and checks["verification_checks_min_3"] and checks["has_plotly_json_block"],
        "score": f"{passed_count}/{len(checks)}",
        "checks": checks,
        "failed_checks": failed_checks,
        "char_count": char_count,
        "step_count": step_count,
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
