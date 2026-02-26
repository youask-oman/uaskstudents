from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import os

from sqlmodel import Session
from app.constants.token_policy_defaults import TOKEN_POLICY_DEFAULTS


@dataclass(frozen=True)
class TokenPolicy:
    text_input_max: int
    text_input_max_chars: int
    text_output_minimal_solve: int
    text_output_minimal_study: int
    text_output_detailed_solve: int
    text_output_detailed_study: int
    text_output_retry_cap_detailed_solve: int
    text_output_retry_cap_detailed_study: int
    text_steps_minimal_solve: int
    text_steps_minimal_study: int
    text_steps_detailed_solve: int
    text_steps_detailed_study: int
    request_system_schema_budget: int
    request_expected_output_budget: int
    ocr_v5_output_max: int
    ocr_image_extract_max: int
    ocr_image_input_max: int
    ocr_image_input_overhead: int
    ocr_pdf_extract_max: int
    ocr_pdf_input_max: int
    ocr_pdf_input_overhead: int
    voice_input_max: int
    voice_input_overhead: int


REQUIRED_CONFIG_KEYS = [
    "tokens.text.input_max",
    "tokens.text.input_max_chars",
    "tokens.text.output_max_minimal_solve",
    "tokens.text.output_max_minimal_study",
    "tokens.text.output_max_detailed_solve",
    "tokens.text.output_max_detailed_study",
    "tokens.text.output_retry_cap_detailed_solve",
    "tokens.text.output_retry_cap_detailed_study",
    "tokens.text.steps_minimal_solve",
    "tokens.text.steps_minimal_study",
    "tokens.text.steps_detailed_solve",
    "tokens.text.steps_detailed_study",
    "tokens.request.system_and_schema_budget",
    "tokens.request.expected_output_budget",
    "tokens.ocr_v5.output_max",
    "tokens.ocr_image.extract_max",
    "tokens.ocr_image.input_max",
    "tokens.ocr_image.input_overhead",
    "tokens.ocr_pdf.extract_max",
    "tokens.ocr_pdf.input_max",
    "tokens.ocr_pdf.input_overhead",
    "tokens.voice.input_max",
    "tokens.voice.input_overhead",
]


def _coerce_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _env_keys_for_token_key(key: str) -> Tuple[str, str]:
    env_key = key.upper().replace(".", "_")
    legacy = key.split(".")[-1]
    return env_key, legacy


def _read_token_value(key: str, default: int) -> int:
    env_key, legacy_key = _env_keys_for_token_key(key)
    raw = os.getenv(env_key)
    if raw is None:
        raw = os.getenv(legacy_key)
    if raw is None:
        raw = str(default)
    return _coerce_int(raw, default)


def get_token_policy(session: Session) -> TokenPolicy:
    """
    Loads token limits from environment variables with defaults from TOKEN_POLICY_DEFAULTS.
    The `session` parameter is retained for call-site compatibility.
    """
    _ = session
    defaults = {k: v[0] for k, v in TOKEN_POLICY_DEFAULTS.items()}
    def get_val(key: str) -> int:
        return _read_token_value(key, int(defaults.get(key, 0)))

    return TokenPolicy(
        text_input_max=get_val("tokens.text.input_max"),
        text_input_max_chars=get_val("tokens.text.input_max_chars"),
        text_output_minimal_solve=get_val("tokens.text.output_max_minimal_solve"),
        text_output_minimal_study=get_val("tokens.text.output_max_minimal_study"),
        text_output_detailed_solve=get_val("tokens.text.output_max_detailed_solve"),
        text_output_detailed_study=get_val("tokens.text.output_max_detailed_study"),
        text_output_retry_cap_detailed_solve=get_val("tokens.text.output_retry_cap_detailed_solve"),
        text_output_retry_cap_detailed_study=get_val("tokens.text.output_retry_cap_detailed_study"),
        text_steps_minimal_solve=get_val("tokens.text.steps_minimal_solve"),
        text_steps_minimal_study=get_val("tokens.text.steps_minimal_study"),
        text_steps_detailed_solve=get_val("tokens.text.steps_detailed_solve"),
        text_steps_detailed_study=get_val("tokens.text.steps_detailed_study"),
        request_system_schema_budget=get_val("tokens.request.system_and_schema_budget"),
        request_expected_output_budget=get_val("tokens.request.expected_output_budget"),
        ocr_v5_output_max=get_val("tokens.ocr_v5.output_max"),
        ocr_image_extract_max=get_val("tokens.ocr_image.extract_max"),
        ocr_image_input_max=get_val("tokens.ocr_image.input_max"),
        ocr_image_input_overhead=get_val("tokens.ocr_image.input_overhead"),
        ocr_pdf_extract_max=get_val("tokens.ocr_pdf.extract_max"),
        ocr_pdf_input_max=get_val("tokens.ocr_pdf.input_max"),
        ocr_pdf_input_overhead=get_val("tokens.ocr_pdf.input_overhead"),
        voice_input_max=get_val("tokens.voice.input_max"),
        voice_input_overhead=get_val("tokens.voice.input_overhead"),
    )


def serialize_token_policy(policy: TokenPolicy) -> Dict[str, object]:
    return {
        "text": {
            "input_max": policy.text_input_max,
            "input_max_chars": policy.text_input_max_chars,
            "output_max": {
                "minimal": {"solve": policy.text_output_minimal_solve, "study": policy.text_output_minimal_study},
                "detailed": {"solve": policy.text_output_detailed_solve, "study": policy.text_output_detailed_study},
            },
            "output_retry_cap": {
                "detailed": {
                    "solve": policy.text_output_retry_cap_detailed_solve,
                    "study": policy.text_output_retry_cap_detailed_study,
                }
            },
        },
        "request": {
            "system_and_schema_budget": policy.request_system_schema_budget,
            "expected_output_budget": policy.request_expected_output_budget,
        },
        "ocr_v5": {
            "output_max": policy.ocr_v5_output_max,
        },
        "ocr_image": {
            "extract_max": policy.ocr_image_extract_max,
            "input_max": policy.ocr_image_input_max,
            "input_overhead": policy.ocr_image_input_overhead,
        },
        "ocr_pdf": {
            "extract_max": policy.ocr_pdf_extract_max,
            "input_max": policy.ocr_pdf_input_max,
            "input_overhead": policy.ocr_pdf_input_overhead,
        },
        "voice": {
            "input_max": policy.voice_input_max,
            "input_overhead": policy.voice_input_overhead,
        },
    }
