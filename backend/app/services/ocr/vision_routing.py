from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


VISION_PROVIDER_ALIASES = {
    "pix2txt": "pix2txt",
    "pix2text": "pix2txt",
    "glm_ocr": "glm_ocr",
    "glm-ocr": "glm_ocr",
    "glm": "glm_ocr",
    "openai": "openai",
    "lmm": "openai",
}


@dataclass
class VisionInput:
    images: List[bytes]
    mime_type: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[int] = None
    source: Optional[str] = None


@dataclass
class VisionOptions:
    max_output_tokens: int
    crop_meta: Optional[Dict[str, Any]] = None
    debug: bool = False


@dataclass
class VisionProviderAttempt:
    provider: str
    model: str
    duration_ms: int
    success: bool
    reason: Optional[str] = None


@dataclass
class VisionExtractionResult:
    provider: str
    model: str
    extracted_text: str
    payload: Dict[str, Any]
    blocks: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    token_usage: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    attempts: List[VisionProviderAttempt] = field(default_factory=list)


class VisionOcrProvider(Protocol):
    name: str
    supports_pdf: bool
    supports_image: bool

    async def extract(self, vision_input: VisionInput, options: VisionOptions) -> VisionExtractionResult:
        ...


@dataclass
class VisionRoutingConfig:
    enabled_providers: List[str]
    default_provider_mode: str
    fallback_order: List[str]

    @classmethod
    def from_env(cls) -> "VisionRoutingConfig":
        enabled_raw = os.getenv("VISION_OCR_ENABLED_PROVIDERS") or "pix2txt,openai"
        enabled = [_normalize_provider_token(token) for token in enabled_raw.split(",")]
        enabled = [token for token in enabled if token]
        if not enabled:
            raise RuntimeError("VISION_OCR_ENABLED_PROVIDERS must include at least one provider")

        if not os.getenv("OPENAI_API_KEY"):
            enabled = [provider for provider in enabled if provider != "openai"]

        fallback_raw = os.getenv("VISION_OCR_FALLBACK_ORDER") or ",".join(enabled)
        fallback = [_normalize_provider_token(token) for token in fallback_raw.split(",")]
        fallback = [token for token in fallback if token in enabled]
        if not fallback:
            fallback = enabled.copy()

        mode = (os.getenv("VISION_OCR_DEFAULT_MODE") or "AUTO").strip().upper()
        if mode not in {"AUTO", "AUTO_WITH_FALLBACK", "PIX2TXT", "GLM_OCR", "OPENAI"}:
            mode = "AUTO"

        return cls(
            enabled_providers=enabled,
            default_provider_mode=mode,
            fallback_order=fallback,
        )


def _normalize_provider_token(value: Optional[str]) -> str:
    if not value:
        return ""
    return VISION_PROVIDER_ALIASES.get(value.strip().lower(), "")


def get_openai_ocr_model() -> str:
    model = (os.getenv("VLM_MODEL_OPENA_AI_OCR") or "").strip()
    if not model:
        raise RuntimeError("VLM_MODEL_OPENA_AI_OCR is required")
    return model


def normalize_engine_choice(raw_choice: Optional[str], config: VisionRoutingConfig) -> str:
    if not raw_choice:
        return config.default_provider_mode.lower()
    choice = raw_choice.strip().lower()
    if choice in {"auto", "auto_with_fallback"}:
        return choice
    normalized = _normalize_provider_token(choice)
    if normalized:
        return normalized
    return config.default_provider_mode.lower()


def build_provider_plan(engine_choice: Optional[str], config: VisionRoutingConfig) -> List[str]:
    choice = normalize_engine_choice(engine_choice, config)
    if choice in {"auto", "auto_with_fallback"}:
        return [provider for provider in config.fallback_order if provider in config.enabled_providers]
    return [choice] if choice else [provider for provider in config.fallback_order if provider in config.enabled_providers]
