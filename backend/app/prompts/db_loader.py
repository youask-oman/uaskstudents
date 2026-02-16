import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import case, or_
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    JsonSchemaEntry,
    PromptBinding,
    PromptModeEnum,
    PromptRoleEnum,
    PromptTemplateEntry,
    PromptTierEnum,
)


class PromptBindingLookupError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class PromptBundle:
    prompt_binding_id: str
    global_system_prompt_id: str
    developer_prompt_id: str
    output_schema_id: str
    system_prompt_content: str
    developer_prompt_content: str
    output_schema_json: Dict[str, Any]
    template_versions: Dict[str, Optional[int]]
    max_output_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    system_schema_budget_tokens: Optional[int] = None
    context_budget_tokens: Optional[int] = None
    json_retry_max_output_tokens: Optional[int] = None
    json_retry_max_attempts: Optional[int] = None
    timeout_ms: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None
    plot_annotations_cap: Optional[int] = None
    trim_strategy: Optional[str] = None
    max_steps: Optional[int] = None
    retry_cap_tokens: Optional[int] = None
    features: Optional[Dict[str, Any]] = None
    multipliers: Optional[Dict[str, Any]] = None


_CACHE_TTL_SECONDS = 60
_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    if (time.time() - entry["ts"]) > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return entry["value"]


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = {"ts": time.time(), "value": value}


@contextmanager
def _session_scope(session: Optional[Session] = None):
    if session is not None:
        yield session
        return
    with Session(engine) as db:
        yield db


def _resolve_tier(tier: str) -> PromptTierEnum:
    slug = (tier or "short_steps").strip().lower()
    if "research" in slug or slug in {"family_standard", "enterprise", "family"}:
        return PromptTierEnum.RESEARCH
    if slug in {"final", "short"}:
        return PromptTierEnum.FINAL
    if slug in {"short_steps", "free", "three_step"}:
        return PromptTierEnum.SHORT_STEPS
    return PromptTierEnum.STANDARD


def _resolve_mode(mode: str) -> PromptModeEnum:
    normalized = (mode or "solve").strip().upper()
    if normalized == PromptModeEnum.VERIFY.value:
        return PromptModeEnum.VERIFY
    if normalized == PromptModeEnum.PLOT_TRIGGER.value:
        return PromptModeEnum.PLOT_TRIGGER
    if normalized == PromptModeEnum.PLOT_SPEC.value:
        return PromptModeEnum.PLOT_SPEC
    return PromptModeEnum.SOLVE


def resolve_prompt_bundle(
    provider: str,
    tier: str,
    mode: str,
    db_session: Optional[Session],
) -> PromptBundle:
    if db_session is None:
        raise PromptBindingLookupError(
            "DB_CONTEXT_REQUIRED_FOR_PROMPTS",
            "Prompt resolution requires a DB session.",
            {"provider": provider, "tier": tier, "mode": mode},
        )

    tier_enum = _resolve_tier(tier)
    mode_enum = _resolve_mode(mode)
    provider_normalized = (provider or "openai").strip().lower()
    cache_key = f"bundle:{provider_normalized}:{tier_enum.value}:{mode_enum.value}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    binding = db_session.exec(
        select(PromptBinding)
        .where(PromptBinding.tier == tier_enum)
        .where(PromptBinding.mode == mode_enum)
        .where(PromptBinding.is_active == True)
        .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
    ).first()
    if not binding:
        raise PromptBindingLookupError(
            "PROMPT_BINDING_NOT_FOUND",
            f"No active prompt binding found for tier={tier_enum.value} mode={mode_enum.value}.",
            {"provider": provider_normalized, "tier": tier_enum.value, "mode": mode_enum.value},
        )

    system_entry = db_session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == binding.global_system_prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .where(PromptTemplateEntry.role.in_([PromptRoleEnum.SYSTEM, PromptRoleEnum.DEVELOPER]))
        .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
    ).first()
    if not system_entry:
        raise PromptBindingLookupError(
            "PROMPT_TEMPLATE_NOT_FOUND",
            f"Missing system prompt template: {binding.global_system_prompt_id}",
            {
                "provider": provider_normalized,
                "tier": tier_enum.value,
                "mode": mode_enum.value,
                "prompt_id": binding.global_system_prompt_id,
                "role": PromptRoleEnum.SYSTEM.value,
            },
        )

    if mode_enum == PromptModeEnum.SOLVE:
        developer_entry = db_session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
            .where(PromptTemplateEntry.mode == mode_enum)
            .where(PromptTemplateEntry.tier == tier_enum)
            .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
        ).first()
        # Fallback: try without tier filter if tier-specific not found
        if not developer_entry:
            developer_entry = db_session.exec(
                select(PromptTemplateEntry)
                .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
                .where(PromptTemplateEntry.is_active == True)
                .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
                .where(PromptTemplateEntry.mode == mode_enum)
                .where(or_(PromptTemplateEntry.tier == tier_enum, PromptTemplateEntry.tier.is_(None)))
                .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
            ).first()
        if not developer_entry:
            raise PromptBindingLookupError(
                "PROMPT_TEMPLATE_TIER_MISSING",
                (
                    "Missing tier-specific developer prompt template for SOLVE mode: "
                    f"prompt_id={binding.developer_prompt_id} tier={tier_enum.value}"
                ),
                {
                    "provider": provider_normalized,
                    "tier": tier_enum.value,
                    "mode": mode_enum.value,
                    "prompt_id": binding.developer_prompt_id,
                    "role": PromptRoleEnum.DEVELOPER.value,
                },
            )
    else:
        tier_match_priority = case((PromptTemplateEntry.tier == tier_enum, 1), else_=0)
        developer_entry = db_session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
            .where(PromptTemplateEntry.mode == mode_enum)
            .where(or_(PromptTemplateEntry.tier == tier_enum, PromptTemplateEntry.tier.is_(None)))
            .order_by(tier_match_priority.desc(), PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
        ).first()
        if not developer_entry:
            raise PromptBindingLookupError(
                "PROMPT_TEMPLATE_NOT_FOUND",
                f"Missing developer prompt template: {binding.developer_prompt_id}",
                {
                    "provider": provider_normalized,
                    "tier": tier_enum.value,
                    "mode": mode_enum.value,
                    "prompt_id": binding.developer_prompt_id,
                    "role": PromptRoleEnum.DEVELOPER.value,
                },
            )

    schema_entry = db_session.exec(
        select(JsonSchemaEntry)
        .where(JsonSchemaEntry.schema_id == binding.output_schema_id)
        .where(JsonSchemaEntry.is_active == True)
        .order_by(JsonSchemaEntry.version.desc(), JsonSchemaEntry.id.desc())
    ).first()
    if not schema_entry:
        raise PromptBindingLookupError(
            "OUTPUT_SCHEMA_NOT_FOUND",
            f"Missing active output schema: {binding.output_schema_id}",
            {
                "provider": provider_normalized,
                "tier": tier_enum.value,
                "mode": mode_enum.value,
                "schema_id": binding.output_schema_id,
            },
        )

    bundle = PromptBundle(
        prompt_binding_id=binding.id,
        global_system_prompt_id=binding.global_system_prompt_id,
        developer_prompt_id=binding.developer_prompt_id,
        output_schema_id=binding.output_schema_id,
        system_prompt_content=system_entry.content,
        developer_prompt_content=developer_entry.content,
        output_schema_json=schema_entry.content if isinstance(schema_entry.content, dict) else {},
        template_versions={
            "system": system_entry.version,
            "developer": developer_entry.version,
            "schema": schema_entry.version,
        },
        max_output_tokens=binding.max_output_tokens,
        max_input_tokens=binding.max_input_tokens,
        system_schema_budget_tokens=binding.system_schema_budget_tokens,
        context_budget_tokens=binding.context_budget_tokens,
        json_retry_max_output_tokens=binding.json_retry_max_output_tokens,
        json_retry_max_attempts=binding.json_retry_max_attempts,
        timeout_ms=binding.timeout_ms,
        temperature=binding.temperature,
        top_p=binding.top_p,
        plot_points_cap=binding.plot_points_cap,
        plot_traces_cap=binding.plot_traces_cap,
        plot_annotations_cap=binding.plot_annotations_cap,
        trim_strategy=binding.trim_strategy.value if binding.trim_strategy else None,
        max_steps=binding.max_steps,
        retry_cap_tokens=binding.retry_cap_tokens,
        features=binding.features if isinstance(binding.features, dict) else {},
        multipliers=binding.multipliers if isinstance(binding.multipliers, dict) else {},
    )
    _cache_set(cache_key, bundle)
    return bundle


def get_active_binding(
    tier: str,
    mode: str,
    session: Optional[Session] = None,
    provider: str = "openai",
) -> PromptBinding:
    with _session_scope(session) as db:
        bundle = resolve_prompt_bundle(provider=provider, tier=tier, mode=mode, db_session=db)
        binding = db.get(PromptBinding, bundle.prompt_binding_id)
        if not binding:
            raise PromptBindingLookupError(
                "PROMPT_BINDING_NOT_FOUND",
                f"Binding not found by id: {bundle.prompt_binding_id}",
                {"provider": provider, "tier": tier, "mode": mode},
            )
        return binding


def get_prompt_content(prompt_id: str, session: Optional[Session] = None) -> PromptTemplateEntry:
    key = f"prompt:{prompt_id}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    with _session_scope(session) as db:
        entry = db.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
        ).first()
    if not entry:
        raise PromptBindingLookupError(
            "PROMPT_TEMPLATE_NOT_FOUND",
            f"Missing active prompt template: prompt_id={prompt_id}",
            {"prompt_id": prompt_id},
        )
    _cache_set(key, entry)
    return entry


def get_output_schema(schema_id: str, session: Optional[Session] = None) -> JsonSchemaEntry:
    key = f"schema:{schema_id}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    with _session_scope(session) as db:
        entry = db.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == schema_id)
            .where(JsonSchemaEntry.is_active == True)
            .order_by(JsonSchemaEntry.version.desc(), JsonSchemaEntry.id.desc())
        ).first()
    if not entry:
        raise PromptBindingLookupError(
            "OUTPUT_SCHEMA_NOT_FOUND",
            f"Missing active output schema: schema_id={schema_id}",
            {"schema_id": schema_id},
        )
    _cache_set(key, entry)
    return entry


def load_prompt_bundle(
    tier: str,
    mode: str,
    session: Optional[Session] = None,
    provider: str = "openai",
) -> Dict[str, Any]:
    with _session_scope(session) as db:
        bundle = resolve_prompt_bundle(
            provider=provider,
            tier=tier,
            mode=mode,
            db_session=db,
        )

    return {
        "binding": {
            "id": bundle.prompt_binding_id,
            "global_system_prompt_id": bundle.global_system_prompt_id,
            "developer_prompt_id": bundle.developer_prompt_id,
            "output_schema_id": bundle.output_schema_id,
            "max_output_tokens": bundle.max_output_tokens,
            "max_input_tokens": bundle.max_input_tokens,
            "system_schema_budget_tokens": bundle.system_schema_budget_tokens,
            "context_budget_tokens": bundle.context_budget_tokens,
            "json_retry_max_output_tokens": bundle.json_retry_max_output_tokens,
            "json_retry_max_attempts": bundle.json_retry_max_attempts,
            "timeout_ms": bundle.timeout_ms,
            "temperature": bundle.temperature,
            "top_p": bundle.top_p,
            "plot_points_cap": bundle.plot_points_cap,
            "plot_traces_cap": bundle.plot_traces_cap,
            "plot_annotations_cap": bundle.plot_annotations_cap,
            "trim_strategy": bundle.trim_strategy,
            "max_steps": bundle.max_steps,
            "retry_cap_tokens": bundle.retry_cap_tokens,
            "features": bundle.features or {},
            "multipliers": bundle.multipliers or {},
        },
        "system_prompt": bundle.system_prompt_content,
        "developer_prompt": bundle.developer_prompt_content,
        "schema": bundle.output_schema_json,
        "meta": {
            "binding_id": bundle.prompt_binding_id,
            "global_system_prompt_id": bundle.global_system_prompt_id,
            "developer_prompt_id": bundle.developer_prompt_id,
            "output_schema_id": bundle.output_schema_id,
            "global_system_prompt_version": bundle.template_versions.get("system"),
            "developer_prompt_version": bundle.template_versions.get("developer"),
            "output_schema_version": bundle.template_versions.get("schema"),
        },
    }


def invalidate_cache() -> None:
    _CACHE.clear()
