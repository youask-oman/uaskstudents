from typing import Dict, Any
from sqlmodel import Session, select
import time

from app.models import PromptBinding, PromptTemplateEntry, JsonSchemaEntry, PromptTierEnum, PromptModeEnum
from app.services.prompt_registry_service import PromptRegistryError


class PromptManager:
    CACHE_TTL_SECONDS = 60

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ts: Dict[str, float] = {}

    def _cache_key(self, tier: PromptTierEnum, mode: PromptModeEnum) -> str:
        return f"{tier.value}:{mode.value}"

    def get_binding(self, session: Session, tier: PromptTierEnum, mode: PromptModeEnum) -> Dict[str, Any]:
        key = self._cache_key(tier, mode)
        now = time.time()

        # Return cached if valid
        if key in self._cache and (now - self._cache_ts.get(key, 0)) < self.CACHE_TTL_SECONDS:
            return self._cache[key]

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

        result = {
            "binding": binding,
            "global_system_prompt": global_prompt.content,
            "developer_prompt": developer_prompt.content,
            "schema": schema_entry.content,
        }

        # Update cache
        self._cache[key] = result
        self._cache_ts[key] = now

        return result

    def invalidate_cache(self, tier: PromptTierEnum = None, mode: PromptModeEnum = None):
        """Clear cache entries. Call after admin edits."""
        if tier and mode:
            key = self._cache_key(tier, mode)
            self._cache.pop(key, None)
            self._cache_ts.pop(key, None)
        else:
            self._cache.clear()
            self._cache_ts.clear()


prompt_manager = PromptManager()

