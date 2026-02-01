from typing import Dict, Any
from sqlmodel import Session, select

from app.models import PromptBinding, PromptTemplateEntry, JsonSchemaEntry, PromptTierEnum, PromptModeEnum
from app.services.prompt_registry_service import PromptRegistryError


class PromptManager:
    def get_binding(self, session: Session, tier: PromptTierEnum, mode: PromptModeEnum) -> Dict[str, Any]:
        binding = session.exec(
            select(PromptBinding)
            .where(PromptBinding.tier == tier)
            .where(PromptBinding.mode == mode)
            .where(PromptBinding.is_active == True)
            .order_by(PromptBinding.updated_at.desc())
        ).first()
        if not binding:
            raise PromptRegistryError(f"No active binding for tier={tier.value} mode={mode.value}")

        global_prompt = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == binding.global_system_prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.version.desc())
        ).first()
        developer_prompt = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.version.desc())
        ).first()
        schema_entry = session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == binding.output_schema_id)
            .where(JsonSchemaEntry.is_active == True)
            .order_by(JsonSchemaEntry.version.desc())
        ).first()

        if not global_prompt or not developer_prompt or not schema_entry:
            raise PromptRegistryError("Binding references missing prompt or schema entries.")

        return {
            "binding": binding,
            "global_system_prompt": global_prompt.content,
            "developer_prompt": developer_prompt.content,
            "schema": schema_entry.content,
        }


prompt_manager = PromptManager()
