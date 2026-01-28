from __future__ import annotations

from typing import Dict, Tuple

TokenPolicyDefault = Tuple[int, str]

TOKEN_POLICY_DEFAULTS: Dict[str, TokenPolicyDefault] = {
    "tokens.text.input_max": (1800, "Max input tokens for text solve"),
    "tokens.text.input_max_chars": (3000, "Max input characters for text solve"),
    "tokens.text.output_max_minimal_solve": (700, "Max output tokens for minimal solve"),
    "tokens.text.output_max_minimal_study": (1200, "Max output tokens for minimal study"),
    "tokens.text.output_max_detailed_solve": (4500, "Max output tokens for detailed solve"),
    "tokens.text.output_max_detailed_study": (3500, "Max output tokens for detailed study"),
    "tokens.text.output_retry_cap_detailed_solve": (3200, "Retry max output tokens for detailed solve"),
    "tokens.text.output_retry_cap_detailed_study": (3600, "Retry max output tokens for detailed study"),
    "tokens.text.steps_minimal_solve": (2, "Max steps for minimal solve"),
    "tokens.text.steps_minimal_study": (3, "Max steps for minimal study"),
    "tokens.text.steps_detailed_solve": (25, "Max steps for detailed solve"),
    "tokens.text.steps_detailed_study": (20, "Max steps for detailed study"),
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
