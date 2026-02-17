from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
from dataclasses import dataclass
from sqlmodel import Session, select

from app.models import PromptTemplateEntry, JsonSchemaEntry
from app.services.admin_config_service import admin_config_service
from app.services.prompt_registry_service import prompt_registry_service


OCR_CONFIG_TYPE = "ocr_configuration"


@dataclass
class OcrRuntimeConfig:
    local_engine_enabled: bool = True
    openai_engine_enabled: bool = True
    openai_model: str = ""
    openai_system_prompt_key: str = "openai_ocr_system_prompt_v1.txt"
    openai_schema_key: str = "openai_image_extract_v1.schema.json"
    dedupe_window_hours: int = 24
    ocr_hold_ttl_minutes: int = 10
    rate_limit_extract_per_min: int = 10
    local_ocr_credit: int = 2
    openai_ocr_credit: int = 3
    solve_credit: int = 3

    def resolved_openai_model(self) -> str:
        model = (os.getenv("OPENAI_MODEL_DEFAULT") or "").strip() or "gpt-5-mini"
        if model != "gpt-5-mini":
            raise RuntimeError(f"OPENAI_MODEL_DEFAULT must be 'gpt-5-mini', got '{model}'")
        return model


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _merge_config(raw: Dict[str, Any]) -> OcrRuntimeConfig:
    cfg = OcrRuntimeConfig()
    if not isinstance(raw, dict):
        return cfg
    cfg.local_engine_enabled = _coerce_bool(raw.get("local_engine_enabled"), cfg.local_engine_enabled)
    cfg.openai_engine_enabled = _coerce_bool(raw.get("openai_engine_enabled"), cfg.openai_engine_enabled)
    cfg.openai_model = str(raw.get("openai_model") or cfg.openai_model)
    cfg.openai_system_prompt_key = str(raw.get("openai_system_prompt_key") or cfg.openai_system_prompt_key)
    cfg.openai_schema_key = str(raw.get("openai_schema_key") or cfg.openai_schema_key)
    cfg.dedupe_window_hours = _coerce_int(raw.get("dedupe_window_hours"), cfg.dedupe_window_hours)
    cfg.ocr_hold_ttl_minutes = _coerce_int(raw.get("ocr_hold_ttl_minutes"), cfg.ocr_hold_ttl_minutes)
    cfg.rate_limit_extract_per_min = _coerce_int(raw.get("rate_limit_extract_per_min"), cfg.rate_limit_extract_per_min)
    cfg.local_ocr_credit = _coerce_int(raw.get("local_ocr_credit"), cfg.local_ocr_credit)
    cfg.openai_ocr_credit = _coerce_int(raw.get("openai_ocr_credit"), cfg.openai_ocr_credit)
    cfg.solve_credit = _coerce_int(raw.get("solve_credit"), cfg.solve_credit)
    return cfg


def get_active_ocr_config(session: Session) -> OcrRuntimeConfig:
    raw = admin_config_service.get_active_config(session, OCR_CONFIG_TYPE)
    return _merge_config(raw)


def resolve_prompt_entry(session: Session, key: str) -> Optional[PromptTemplateEntry]:
    if not key:
        return None
    entry = prompt_registry_service.get_active_prompt(session, key)
    if entry:
        return entry
    # Fallback to .txt suffix when admin provides base key
    if not key.endswith(".txt"):
        entry = prompt_registry_service.get_active_prompt(session, f"{key}.txt")
        if entry:
            return entry
    return None


def resolve_schema_entry(session: Session, key: str) -> Optional[JsonSchemaEntry]:
    if not key:
        return None
    entry = prompt_registry_service.get_active_schema(session, key)
    if entry:
        return entry
    if not key.endswith(".schema.json"):
        entry = prompt_registry_service.get_active_schema(session, f"{key}.schema.json")
        if entry:
            return entry
    # Fallback to content.name match (for seed data where schema_id differs)
    candidates = session.exec(select(JsonSchemaEntry).where(JsonSchemaEntry.is_active == True)).all()
    for candidate in candidates:
        content = candidate.content if isinstance(candidate.content, dict) else {}
        if content.get("name") == key:
            return candidate
    return None


def list_active_prompt_entries(session: Session) -> List[PromptTemplateEntry]:
    return session.exec(select(PromptTemplateEntry).where(PromptTemplateEntry.is_active == True)).all()


def list_active_schema_entries(session: Session) -> List[JsonSchemaEntry]:
    return session.exec(select(JsonSchemaEntry).where(JsonSchemaEntry.is_active == True)).all()
