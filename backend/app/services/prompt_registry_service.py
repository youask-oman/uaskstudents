import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlmodel import Session, select
from jsonschema import Draft202012Validator

from app.models import (
    PromptTemplateEntry,
    JsonSchemaEntry,
    PromptBinding,
    PromptTierEnum,
    PromptModeEnum,
    PromptRoleEnum,
    TrimStrategyEnum,
)


class PromptRegistryError(Exception):
    pass


class PromptRegistryService:
    """
    All prompt IDs loaded from environment variables or database.
    NO hardcoded prompt IDs allowed.
    """
    
    def _content_checksum(self, content: str) -> str:
        return hashlib.sha256((content or "").strip().encode("utf-8")).hexdigest()

    def _upsert_prompt_if_checksum_differs(
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
        if current and self._content_checksum(current.content) == self._content_checksum(content):
            return current
        return self.update_prompt(
            session=session,
            prompt_id=prompt_id,
            content=content,
            tier=tier,
            mode=mode,
            role=role,
            updated_by=updated_by,
        )

    def _deactivate_prompt_ids(
        self,
        session: Session,
        prompt_ids: Tuple[str, ...],
        updated_by: Optional[str],
    ) -> None:
        if not prompt_ids:
            return
        rows = session.exec(
            select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id.in_(prompt_ids))
        ).all()
        changed = False
        for row in rows:
            if row.is_active:
                row.is_active = False
                row.updated_at = datetime.utcnow()
                row.updated_by = updated_by
                session.add(row)
                changed = True
        if changed:
            session.commit()

    def _deactivate_schema_ids(
        self,
        session: Session,
        schema_ids: Tuple[str, ...],
        updated_by: Optional[str],
    ) -> None:
        if not schema_ids:
            return
        rows = session.exec(
            select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id.in_(schema_ids))
        ).all()
        changed = False
        for row in rows:
            if row.is_active:
                row.is_active = False
                row.updated_at = datetime.utcnow()
                row.updated_by = updated_by
                session.add(row)
                changed = True
        if changed:
            session.commit()

    def _ensure_prompt_exists(
        self,
        session: Session,
        prompt_id: str,
        content: str,
        tier: Optional[PromptTierEnum],
        mode: PromptModeEnum,
        role: str,
        updated_by: Optional[str],
    ) -> PromptTemplateEntry:
        active = self.get_active_prompt(session, prompt_id)
        if active:
            return active

        versions = self.get_prompt_versions(session, prompt_id)
        if versions:
            latest = versions[0]
            latest.is_active = True
            latest.updated_at = datetime.utcnow()
            latest.updated_by = updated_by
            session.add(latest)
            session.commit()
            session.refresh(latest)
            return latest

        return self.update_prompt(
            session=session,
            prompt_id=prompt_id,
            content=content,
            tier=tier,
            mode=mode,
            role=role,
            updated_by=updated_by,
        )

    def _ensure_schema_exists(
        self,
        session: Session,
        schema_id: str,
        content: Dict[str, Any],
        updated_by: Optional[str],
    ) -> JsonSchemaEntry:
        active = self.get_active_schema(session, schema_id)
        if active:
            return active

        versions = self.get_schema_versions(session, schema_id)
        if versions:
            latest = versions[0]
            latest.is_active = True
            latest.updated_at = datetime.utcnow()
            latest.updated_by = updated_by
            session.add(latest)
            session.commit()
            session.refresh(latest)
            return latest

        return self.update_schema(
            session=session,
            schema_id=schema_id,
            content=content,
            updated_by=updated_by,
        )

    def audit_active_bindings(self, session: Session, expect_full_matrix: bool = True) -> Dict[str, Any]:
        """
        Validate that active prompt bindings are complete and resolvable.
        Returns a report with issues but does not mutate data.
        """
        bindings = session.exec(
            select(PromptBinding)
            .where(PromptBinding.is_active == True)
            .order_by(PromptBinding.tier.asc(), PromptBinding.mode.asc(), PromptBinding.updated_at.desc())
        ).all()

        issues = []
        key_latest: Dict[Tuple[str, str], PromptBinding] = {}

        for binding in bindings:
            key = (binding.tier.value, binding.mode.value)
            if key in key_latest:
                issues.append({
                    "type": "duplicate_active_binding",
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "binding_id": binding.id,
                })
                continue
            key_latest[key] = binding

            global_prompt = self.get_active_prompt(session, binding.global_system_prompt_id)
            developer_prompt = self.get_active_prompt(session, binding.developer_prompt_id)
            schema_entry = self.get_active_schema(session, binding.output_schema_id)

            if not global_prompt:
                issues.append({
                    "type": "missing_global_prompt",
                    "binding_id": binding.id,
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "prompt_id": binding.global_system_prompt_id,
                })
            if not developer_prompt:
                issues.append({
                    "type": "missing_developer_prompt",
                    "binding_id": binding.id,
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "prompt_id": binding.developer_prompt_id,
                })
            if not schema_entry:
                issues.append({
                    "type": "missing_output_schema",
                    "binding_id": binding.id,
                    "tier": binding.tier.value,
                    "mode": binding.mode.value,
                    "schema_id": binding.output_schema_id,
                })

        found_pairs = set(key_latest.keys())
        if expect_full_matrix:
            expected_pairs = {(tier.value, mode.value) for tier in PromptTierEnum for mode in PromptModeEnum}
            for tier_value, mode_value in sorted(expected_pairs - found_pairs):
                issues.append({
                    "type": "missing_binding_pair",
                    "tier": tier_value,
                    "mode": mode_value,
                })

        return {
            "ok": len(issues) == 0,
            "active_bindings": len(bindings),
            "active_binding_pairs": len(found_pairs),
            "issues": issues,
        }

    def _resolve_tier(self, tier_slug: str) -> PromptTierEnum:
        slug = (tier_slug or "").lower()
        if "research" in slug:
            return PromptTierEnum.RESEARCH
        if "standard" in slug or "family" in slug or "pro" in slug:
            return PromptTierEnum.STANDARD
        return PromptTierEnum.FREE

    def _resolve_mode(self, mode: str) -> PromptModeEnum:
        mode = (mode or "solve").lower()
        if mode in {"ocr_extract", "ocr"}:
            return PromptModeEnum.OCR_EXTRACT
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
        """
        Validate schema for both JSON Schema compliance and OpenAI compatibility.
        Returns error message if invalid, None if valid.
        """
        # Check for invalid type declarations first (OpenAI-specific)
        from app.utils.schema_validator import validate_openai_schema_wrapper
        type_issues = validate_openai_schema_wrapper(schema_content)
        if type_issues:
            error_details = "; ".join([f"{path}: {msg}" for path, msg in type_issues[:3]])
            return f"Invalid type declarations: {error_details}"
        
        # Then validate JSON Schema structure per draft 2020-12
        schema_for_validation = self.schema_object_for_validation(schema_content)
        try:
            Draft202012Validator.check_schema(schema_for_validation)
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

        versions = self.get_prompt_versions(session, prompt_id)
        max_version = max((entry.version for entry in versions), default=0)
        next_version = self._next_version(max_version)
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

    def _pick_replacement_prompt(
        self,
        session: Session,
        *,
        role: PromptRoleEnum,
        mode: PromptModeEnum,
        tier: Optional[PromptTierEnum],
        exclude_prompt_id: str,
    ) -> Optional[PromptTemplateEntry]:
        candidates = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.is_active == True)
            .where(PromptTemplateEntry.role == role)
            .where(PromptTemplateEntry.mode == mode)
            .where(PromptTemplateEntry.prompt_id != exclude_prompt_id)
            .order_by(PromptTemplateEntry.updated_at.desc(), PromptTemplateEntry.id.desc())
        ).all()
        if not candidates:
            return None

        def _tier_rank(entry: PromptTemplateEntry) -> int:
            if tier is None:
                return 0 if entry.tier is None else 1
            if entry.tier == tier:
                return 0
            if entry.tier is None:
                return 1
            return 2

        candidates.sort(key=_tier_rank)
        return candidates[0]

    def delete_prompt(
        self,
        session: Session,
        prompt_id: str,
        updated_by: Optional[str],
    ) -> Dict[str, int]:
        rows = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .order_by(PromptTemplateEntry.version.desc())
        ).all()
        if not rows:
            raise PromptRegistryError("Prompt not found.")

        active_bindings = session.exec(
            select(PromptBinding).where(PromptBinding.is_active == True)
        ).all()
        impacted_bindings = [
            binding
            for binding in active_bindings
            if (
                binding.global_system_prompt_id == prompt_id
                or binding.developer_prompt_id == prompt_id
            )
        ]

        rebound_bindings = 0
        deactivated_bindings = 0

        for binding in impacted_bindings:
            changed = False
            replaced = False
            deactivate = False

            if binding.global_system_prompt_id == prompt_id:
                replacement = self._pick_replacement_prompt(
                    session=session,
                    role=PromptRoleEnum.SYSTEM,
                    mode=binding.mode,
                    tier=None,
                    exclude_prompt_id=prompt_id,
                )
                if replacement:
                    binding.global_system_prompt_id = replacement.prompt_id
                    replaced = True
                    changed = True
                else:
                    deactivate = True

            if not deactivate and binding.developer_prompt_id == prompt_id:
                replacement = self._pick_replacement_prompt(
                    session=session,
                    role=PromptRoleEnum.DEVELOPER,
                    mode=binding.mode,
                    tier=binding.tier,
                    exclude_prompt_id=prompt_id,
                )
                if replacement:
                    binding.developer_prompt_id = replacement.prompt_id
                    replaced = True
                    changed = True
                else:
                    deactivate = True

            if deactivate:
                binding.is_active = False
                changed = True
                deactivated_bindings += 1
            elif replaced:
                rebound_bindings += 1

            if changed:
                binding.updated_at = datetime.utcnow()
                binding.updated_by = updated_by
                session.add(binding)

        deleted_versions = len(rows)
        for row in rows:
            session.delete(row)

        session.commit()
        return {
            "deleted_versions": deleted_versions,
            "rebound_bindings": rebound_bindings,
            "deactivated_bindings": deactivated_bindings,
        }

    def _pick_replacement_schema(
        self,
        session: Session,
        *,
        mode: PromptModeEnum,
        exclude_schema_id: str,
    ) -> Optional[JsonSchemaEntry]:
        same_mode_bindings = session.exec(
            select(PromptBinding)
            .where(PromptBinding.is_active == True)
            .where(PromptBinding.mode == mode)
            .where(PromptBinding.output_schema_id != exclude_schema_id)
            .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
        ).all()
        for binding in same_mode_bindings:
            schema_entry = self.get_active_schema(session, binding.output_schema_id)
            if schema_entry:
                return schema_entry

        return session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.is_active == True)
            .where(JsonSchemaEntry.schema_id != exclude_schema_id)
            .order_by(JsonSchemaEntry.updated_at.desc(), JsonSchemaEntry.id.desc())
        ).first()

    def delete_schema(
        self,
        session: Session,
        schema_id: str,
        updated_by: Optional[str],
    ) -> Dict[str, int]:
        rows = session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == schema_id)
            .order_by(JsonSchemaEntry.version.desc())
        ).all()
        if not rows:
            raise PromptRegistryError("Schema not found.")

        impacted_bindings = session.exec(
            select(PromptBinding)
            .where(PromptBinding.is_active == True)
            .where(PromptBinding.output_schema_id == schema_id)
            .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
        ).all()

        rebound_bindings = 0
        deactivated_bindings = 0

        for binding in impacted_bindings:
            replacement = self._pick_replacement_schema(
                session=session,
                mode=binding.mode,
                exclude_schema_id=schema_id,
            )
            if replacement:
                binding.output_schema_id = replacement.schema_id
                rebound_bindings += 1
            else:
                binding.is_active = False
                deactivated_bindings += 1
            binding.updated_at = datetime.utcnow()
            binding.updated_by = updated_by
            session.add(binding)

        deleted_versions = len(rows)
        for row in rows:
            session.delete(row)

        session.commit()
        return {
            "deleted_versions": deleted_versions,
            "rebound_bindings": rebound_bindings,
            "deactivated_bindings": deactivated_bindings,
        }

    def update_schema(
        self,
        session: Session,
        schema_id: str,
        content: Dict[str, Any],
        updated_by: Optional[str],
    ) -> JsonSchemaEntry:
        # Validate schema types before saving (reject invalid types like "None", null)
        from app.utils.schema_validator import validate_openai_schema_wrapper, SchemaValidationError
        type_issues = validate_openai_schema_wrapper(content)
        if type_issues:
            error_details = "; ".join([f"{path}: {msg}" for path, msg in type_issues[:3]])
            raise PromptRegistryError(
                f"Schema contains invalid type declarations: {error_details}"
            )
        
        current = self.get_active_schema(session, schema_id)
        if current and json.dumps(current.content, sort_keys=True) == json.dumps(content, sort_keys=True):
            return current

        versions = self.get_schema_versions(session, schema_id)
        max_version = max((entry.version for entry in versions), default=0)
        next_version = self._next_version(max_version)
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

    def schema_object_for_validation(self, schema_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept either raw JSON Schema or OpenAI wrapper payloads and return the
        JSON Schema object used for validation, without mutating stored content.
        """
        if not isinstance(schema_content, dict):
            return schema_content

        direct = schema_content.get("schema")
        if isinstance(direct, dict):
            return direct

        json_schema_block = schema_content.get("json_schema")
        if isinstance(json_schema_block, dict):
            if isinstance(json_schema_block.get("schema"), dict):
                return json_schema_block["schema"]
            return json_schema_block

        return schema_content

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
        max_output_tokens: Optional[int] = None,
        max_input_tokens: Optional[int] = None,
        system_schema_budget_tokens: Optional[int] = None,
        context_budget_tokens: Optional[int] = None,
        json_retry_max_output_tokens: Optional[int] = None,
        json_retry_max_attempts: Optional[int] = None,
        timeout_ms: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        plot_points_cap: Optional[int] = None,
        plot_traces_cap: Optional[int] = None,
        plot_annotations_cap: Optional[int] = None,
        trim_strategy: Optional[TrimStrategyEnum] = None,
        max_steps: Optional[int] = None,
        retry_cap_tokens: Optional[int] = None,
    ) -> PromptBinding:
        active_rows = session.exec(
            select(PromptBinding)
            .where(PromptBinding.tier == tier)
            .where(PromptBinding.mode == mode)
            .where(PromptBinding.is_active == True)
        ).all()
        for row in active_rows:
            row.is_active = False
            row.updated_at = datetime.utcnow()
            row.updated_by = updated_by
            session.add(row)

        entry = PromptBinding(
            tier=tier,
            mode=mode,
            global_system_prompt_id=global_system_prompt_id,
            developer_prompt_id=developer_prompt_id,
            output_schema_id=output_schema_id,
            max_output_tokens=max_output_tokens,
            max_input_tokens=max_input_tokens,
            system_schema_budget_tokens=system_schema_budget_tokens,
            context_budget_tokens=context_budget_tokens,
            json_retry_max_output_tokens=json_retry_max_output_tokens,
            json_retry_max_attempts=json_retry_max_attempts,
            timeout_ms=timeout_ms,
            temperature=temperature,
            top_p=top_p,
            plot_points_cap=plot_points_cap,
            plot_traces_cap=plot_traces_cap,
            plot_annotations_cap=plot_annotations_cap,
            trim_strategy=trim_strategy,
            max_steps=max_steps,
            retry_cap_tokens=retry_cap_tokens,
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


prompt_registry_service = PromptRegistryService()
