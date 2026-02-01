import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlmodel import Session, select
from jsonschema import Draft202012Validator

from app.models import (
    PromptTemplateEntry,
    JsonSchemaEntry,
    PromptBinding,
    PromptTierEnum,
    PromptModeEnum,
)


class PromptRegistryError(Exception):
    pass


class PromptRegistryService:
    def _resolve_tier(self, tier_slug: str) -> PromptTierEnum:
        slug = (tier_slug or "").lower()
        if "research" in slug:
            return PromptTierEnum.RESEARCH
        if "standard" in slug or "family" in slug or "pro" in slug:
            return PromptTierEnum.STANDARD
        return PromptTierEnum.FREE

    def _resolve_mode(self, mode: str) -> PromptModeEnum:
        mode = (mode or "solve").lower()
        if mode in {"verify"}:
            return PromptModeEnum.VERIFY
        if mode in {"plot_trigger"}:
            return PromptModeEnum.PLOT_TRIGGER
        if mode in {"plot_spec"}:
            return PromptModeEnum.PLOT_SPEC
        return PromptModeEnum.SOLVE

    def get_active_prompt(self, session: Session, prompt_id: str) -> Optional[PromptTemplateEntry]:
        return session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.version.desc())
        ).first()

    def get_prompt_versions(self, session: Session, prompt_id: str) -> list:
        return session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .order_by(PromptTemplateEntry.version.desc())
        ).all()

    def get_active_schema(self, session: Session, schema_id: str) -> Optional[JsonSchemaEntry]:
        return session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == schema_id)
            .where(JsonSchemaEntry.is_active == True)
            .order_by(JsonSchemaEntry.version.desc())
        ).first()

    def get_schema_versions(self, session: Session, schema_id: str) -> list:
        return session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == schema_id)
            .order_by(JsonSchemaEntry.version.desc())
        ).all()

    def get_active_binding(self, session: Session, tier: PromptTierEnum, mode: PromptModeEnum) -> Optional[PromptBinding]:
        return session.exec(
            select(PromptBinding)
            .where(PromptBinding.tier == tier)
            .where(PromptBinding.mode == mode)
            .where(PromptBinding.is_active == True)
            .order_by(PromptBinding.updated_at.desc())
        ).first()

    def build_system_prompt(self, global_system: str, developer: str) -> str:
        if not developer:
            return global_system
        return f"{global_system.strip()}\n\n{developer.strip()}"

    def resolve_binding_payload(
        self,
        session: Session,
        tier_slug: str,
        mode: str,
    ) -> Tuple[str, Dict[str, Any], PromptBinding]:
        tier = self._resolve_tier(tier_slug)
        prompt_mode = self._resolve_mode(mode)
        binding = self.get_active_binding(session, tier, prompt_mode)
        if not binding:
            raise PromptRegistryError(f"No active binding for tier={tier.value} mode={prompt_mode.value}")

        global_prompt = self.get_active_prompt(session, binding.global_system_prompt_id)
        developer_prompt = self.get_active_prompt(session, binding.developer_prompt_id)
        schema_entry = self.get_active_schema(session, binding.output_schema_id)

        if not global_prompt or not developer_prompt or not schema_entry:
            raise PromptRegistryError("Binding references missing prompt or schema entries.")

        system_prompt = self.build_system_prompt(global_prompt.content, developer_prompt.content)
        return system_prompt, schema_entry.content, binding

    def validate_schema(self, schema_content: Dict[str, Any]) -> Optional[str]:
        try:
            Draft202012Validator.check_schema(schema_content)
            return None
        except Exception as e:
            return str(e)

    def _next_version(self, existing: Optional[int]) -> int:
        return (existing or 0) + 1

    def update_prompt(
        self,
        session: Session,
        prompt_id: str,
        content: str,
        tier: Optional[PromptTierEnum],
        mode: PromptModeEnum,
        role: str,
        updated_by: Optional[str],
    ) -> PromptTemplateEntry:
        current = self.get_active_prompt(session, prompt_id)
        if current and current.content.strip() == content.strip():
            return current

        next_version = self._next_version(current.version if current else 0)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()

        entry = PromptTemplateEntry(
            prompt_id=prompt_id,
            tier=tier,
            mode=mode,
            role=role,
            content=content,
            version=next_version,
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    def update_schema(
        self,
        session: Session,
        schema_id: str,
        content: Dict[str, Any],
        updated_by: Optional[str],
    ) -> JsonSchemaEntry:
        current = self.get_active_schema(session, schema_id)
        if current and json.dumps(current.content, sort_keys=True) == json.dumps(content, sort_keys=True):
            return current

        next_version = self._next_version(current.version if current else 0)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()

        entry = JsonSchemaEntry(
            schema_id=schema_id,
            content=content,
            version=next_version,
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    def rollback_prompt(self, session: Session, prompt_id: str, version: int, updated_by: Optional[str]) -> PromptTemplateEntry:
        target = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .where(PromptTemplateEntry.version == version)
        ).first()
        if not target:
            raise PromptRegistryError("Prompt version not found.")

        current = self.get_active_prompt(session, prompt_id)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()
            current.updated_by = updated_by

        target.is_active = True
        target.updated_at = datetime.utcnow()
        target.updated_by = updated_by
        session.add(target)
        session.commit()
        session.refresh(target)
        return target

    def rollback_schema(self, session: Session, schema_id: str, version: int, updated_by: Optional[str]) -> JsonSchemaEntry:
        target = session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == schema_id)
            .where(JsonSchemaEntry.version == version)
        ).first()
        if not target:
            raise PromptRegistryError("Schema version not found.")

        current = self.get_active_schema(session, schema_id)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()
            current.updated_by = updated_by

        target.is_active = True
        target.updated_at = datetime.utcnow()
        target.updated_by = updated_by
        session.add(target)
        session.commit()
        session.refresh(target)
        return target

    def activate_binding(
        self,
        session: Session,
        tier: PromptTierEnum,
        mode: PromptModeEnum,
        global_system_prompt_id: str,
        developer_prompt_id: str,
        output_schema_id: str,
        updated_by: Optional[str],
    ) -> PromptBinding:
        current = self.get_active_binding(session, tier, mode)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()
            current.updated_by = updated_by

        entry = PromptBinding(
            tier=tier,
            mode=mode,
            global_system_prompt_id=global_system_prompt_id,
            developer_prompt_id=developer_prompt_id,
            output_schema_id=output_schema_id,
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


prompt_registry_service = PromptRegistryService()
