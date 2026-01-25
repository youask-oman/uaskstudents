from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from sqlmodel import Session, select

from app.models import SystemConfig


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


_DEFAULTS: Dict[str, Tuple[int, str]] = {
    "tokens.text.input_max": (1800, "Max input tokens for text solve"),
    "tokens.text.input_max_chars": (3000, "Max input characters for text solve"),
    "tokens.text.output_max_minimal_solve": (700, "Max output tokens for minimal solve"),
    "tokens.text.output_max_minimal_study": (1200, "Max output tokens for minimal study"),
    "tokens.text.output_max_detailed_solve": (1800, "Max output tokens for detailed solve"),
    "tokens.text.output_max_detailed_study": (2600, "Max output tokens for detailed study"),
    "tokens.text.output_retry_cap_detailed_solve": (2600, "Retry max output tokens for detailed solve"),
    "tokens.text.output_retry_cap_detailed_study": (3600, "Retry max output tokens for detailed study"),
    "tokens.request.system_and_schema_budget": (3500, "Estimated system+schema tokens"),
    "tokens.request.expected_output_budget": (1200, "Expected output tokens for request fit"),
    "tokens.ocr_v5.output_max": (800, "Max output tokens for OCR v5"),
    "tokens.ocr_image.extract_max": (1800, "Max tokens for OCR image extraction"),
    "tokens.ocr_image.input_max": (1400, "Max input tokens for OCR image solve"),
    "tokens.ocr_image.input_overhead": (350, "Input overhead tokens for OCR image solve"),
    "tokens.ocr_pdf.extract_max": (3200, "Max tokens for OCR PDF extraction"),
    "tokens.ocr_pdf.input_max": (1800, "Max input tokens for OCR PDF solve"),
    "tokens.ocr_pdf.input_overhead": (450, "Input overhead tokens for OCR PDF solve"),
    "tokens.voice.input_max": (1200, "Max input tokens for voice solve"),
    "tokens.voice.input_overhead": (150, "Input overhead tokens for voice solve"),
}


def _coerce_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _ensure_config_rows(session: Session) -> Dict[str, int]:
    keys = list(_DEFAULTS.keys())
    existing = {
        row.key: row
        for row in session.exec(select(SystemConfig).where(SystemConfig.key.in_(keys))).all()
    }

    values: Dict[str, int] = {}
    for key, (default_value, description) in _DEFAULTS.items():
        row = existing.get(key)
        if row is None:
            row = SystemConfig(key=key, value=str(default_value), description=description)
            session.add(row)
            values[key] = default_value
            continue

        coerced = _coerce_int(row.value, default_value)
        if str(row.value).strip() != str(coerced):
            row.value = str(coerced)
        if description and not row.description:
            row.description = description
        session.add(row)
        values[key] = coerced

    session.commit()
    return values


def get_token_policy(session: Session) -> TokenPolicy:
    values = _ensure_config_rows(session)
    return TokenPolicy(
        text_input_max=values["tokens.text.input_max"],
        text_input_max_chars=values["tokens.text.input_max_chars"],
        text_output_minimal_solve=values["tokens.text.output_max_minimal_solve"],
        text_output_minimal_study=values["tokens.text.output_max_minimal_study"],
        text_output_detailed_solve=values["tokens.text.output_max_detailed_solve"],
        text_output_detailed_study=values["tokens.text.output_max_detailed_study"],
        text_output_retry_cap_detailed_solve=values["tokens.text.output_retry_cap_detailed_solve"],
        text_output_retry_cap_detailed_study=values["tokens.text.output_retry_cap_detailed_study"],
        request_system_schema_budget=values["tokens.request.system_and_schema_budget"],
        request_expected_output_budget=values["tokens.request.expected_output_budget"],
        ocr_v5_output_max=values["tokens.ocr_v5.output_max"],
        ocr_image_extract_max=values["tokens.ocr_image.extract_max"],
        ocr_image_input_max=values["tokens.ocr_image.input_max"],
        ocr_image_input_overhead=values["tokens.ocr_image.input_overhead"],
        ocr_pdf_extract_max=values["tokens.ocr_pdf.extract_max"],
        ocr_pdf_input_max=values["tokens.ocr_pdf.input_max"],
        ocr_pdf_input_overhead=values["tokens.ocr_pdf.input_overhead"],
        voice_input_max=values["tokens.voice.input_max"],
        voice_input_overhead=values["tokens.voice.input_overhead"],
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
