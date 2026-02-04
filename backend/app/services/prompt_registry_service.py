import hashlib
import json
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
)


class PromptRegistryError(Exception):
    pass


class PromptRegistryService:
    OCR_EXTRACT_OPENAI_SYSTEM_PROMPT_ID = "openai_ocr_system_prompt_v1"
    OCR_EXTRACT_OPENAI_SCHEMA_ID = "youask_math_solver_openai_ocr_v1"
    STANDARD_SOLVE_PROMPT_ID = "solve_standard_extreme_detailed_v1"
    STANDARD_SOLVE_SCHEMA_ID = "youask_math_solver_standard_solve_extreme_v1"
    STANDARD_SOLVE_GLOBAL_SYSTEM_ID = "global_system_prompt_v1"
    FREEFORM_SOLVE_PROMPT_ID = "free_form_math_standard_detailed_v1"
    FREEFORM_SOLVE_FREE_PROMPT_ID = "free_form_math_free_fast_v1"
    FREEFORM_SOLVE_RESEARCH_PROMPT_ID = "free_form_math_research_rigorous_v1"
    FREEFORM_SOLVE_TIER_PROMPT_IDS = {
        PromptTierEnum.FREE: FREEFORM_SOLVE_FREE_PROMPT_ID,
        PromptTierEnum.STANDARD: FREEFORM_SOLVE_PROMPT_ID,
        PromptTierEnum.RESEARCH: FREEFORM_SOLVE_RESEARCH_PROMPT_ID,
    }
    LEGACY_STANDARD_SOLVE_PROMPT_IDS = (
        "solve_standard_moderate_v1",
        "solve_standard_moderate_v2",
    )
    LEGACY_STANDARD_SOLVE_SCHEMA_IDS = (
        "youask_math_solver_standard_solve_v1",
        "youask_math_solver_standard_solve_v2",
    )

    STANDARD_SOLVE_PROMPT_ASSET = "backend/app/prompts/solve_standard_extreme_detailed_v1.txt"
    STANDARD_SOLVE_SCHEMA_ASSET = "backend/app/schemas/youask_math_solver_standard_solve_extreme_v1.json"
    FREEFORM_SOLVE_PROMPT_ASSET = "static_design/sug_prompts_openai/free_form_math_standard_detailed.txt"
    FREEFORM_SOLVE_FREE_PROMPT_ASSET = "static_design/sug_prompts_openai/free_form_math_free_fast_v1.txt"
    FREEFORM_SOLVE_RESEARCH_PROMPT_ASSET = "static_design/sug_prompts_openai/free_form_math_research_rigorous_v1.txt"

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _load_asset_text(self, rel_path: str) -> str:
        path = self._repo_root() / rel_path
        return path.read_text(encoding="utf-8").strip()

    def _load_asset_json(self, rel_path: str) -> Dict[str, Any]:
        path = self._repo_root() / rel_path
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def ensure_ocr_extract_prompts(self, session: Session, updated_by: Optional[str] = "system") -> None:
        """
        Ensure OpenAI OCR prompts/schema exist in prompt_templates.
        These IDs are read by runtime extraction flow and can be edited via registry admin APIs.
        """
        openai_system_prompt = self._load_asset_text(
            "static_design/sug_prompts_openai/openai_ocr_system_prompt_v1.txt"
        )
        openai_schema = self._load_asset_json(
            "static_design/sug_prompts_openai/youask_math_solver_openai_ocr_v1.json"
        )
        self._ensure_prompt_exists(
            session=session,
            prompt_id=self.OCR_EXTRACT_OPENAI_SYSTEM_PROMPT_ID,
            content=openai_system_prompt,
            tier=None,
            mode=PromptModeEnum.SOLVE,
            role=PromptRoleEnum.SYSTEM,
            updated_by=updated_by,
        )
        self._ensure_schema_exists(
            session=session,
            schema_id=self.OCR_EXTRACT_OPENAI_SCHEMA_ID,
            content=openai_schema,
            updated_by=updated_by,
        )

    def ensure_standard_solve_binding(
        self,
        session: Session,
        updated_by: Optional[str] = "system",
    ) -> None:
        """
        Ensure STANDARD/SOLVE defaults to the configured prompt/schema version.
        Runtime solve path still reads prompts/schemas from DB bindings only.
        """
        global_prompt = self.get_active_prompt(session, self.STANDARD_SOLVE_GLOBAL_SYSTEM_ID)
        if not global_prompt:
            raise PromptRegistryError(
                f"Missing required global system prompt: {self.STANDARD_SOLVE_GLOBAL_SYSTEM_ID}"
            )

        standard_prompt = self._load_asset_text(self.STANDARD_SOLVE_PROMPT_ASSET)
        standard_schema = self._load_asset_json(self.STANDARD_SOLVE_SCHEMA_ASSET)
        self.update_prompt(
            session=session,
            prompt_id=self.STANDARD_SOLVE_PROMPT_ID,
            content=standard_prompt,
            tier=PromptTierEnum.STANDARD,
            mode=PromptModeEnum.SOLVE,
            role=PromptRoleEnum.DEVELOPER,
            updated_by=updated_by,
        )
        self.update_schema(
            session=session,
            schema_id=self.STANDARD_SOLVE_SCHEMA_ID,
            content=standard_schema,
            updated_by=updated_by,
        )
        self._deactivate_prompt_ids(
            session=session,
            prompt_ids=self.LEGACY_STANDARD_SOLVE_PROMPT_IDS,
            updated_by=updated_by,
        )
        self._deactivate_schema_ids(
            session=session,
            schema_ids=self.LEGACY_STANDARD_SOLVE_SCHEMA_IDS,
            updated_by=updated_by,
        )
        target_prompt_id = self.STANDARD_SOLVE_PROMPT_ID
        target_schema_id = self.STANDARD_SOLVE_SCHEMA_ID

        prompt_entry = self.get_active_prompt(session, target_prompt_id)
        if not prompt_entry:
            raise PromptRegistryError(f"Missing developer prompt for STANDARD/SOLVE: {target_prompt_id}")
        schema_entry = self.get_active_schema(session, target_schema_id)
        if not schema_entry:
            raise PromptRegistryError(f"Missing output schema for STANDARD/SOLVE: {target_schema_id}")

        current = self.get_active_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE)
        if (
            current
            and current.global_system_prompt_id == self.STANDARD_SOLVE_GLOBAL_SYSTEM_ID
            and current.developer_prompt_id == target_prompt_id
            and current.output_schema_id == target_schema_id
        ):
            return

        self.activate_binding(
            session=session,
            tier=PromptTierEnum.STANDARD,
            mode=PromptModeEnum.SOLVE,
            global_system_prompt_id=self.STANDARD_SOLVE_GLOBAL_SYSTEM_ID,
            developer_prompt_id=target_prompt_id,
            output_schema_id=target_schema_id,
            updated_by=updated_by,
        )

    def ensure_freeform_solve_prompt(
        self,
        session: Session,
        updated_by: Optional[str] = "system",
    ) -> PromptTemplateEntry:
        content = self._load_asset_text(self.FREEFORM_SOLVE_PROMPT_ASSET)
        return self._upsert_prompt_if_checksum_differs(
            session=session,
            prompt_id=self.FREEFORM_SOLVE_PROMPT_ID,
            content=content,
            tier=PromptTierEnum.STANDARD,
            mode=PromptModeEnum.SOLVE,
            role=PromptRoleEnum.DEVELOPER,
            updated_by=updated_by,
        )

    def ensure_freeform_solve_prompts_by_tier(
        self,
        session: Session,
        updated_by: Optional[str] = "system",
    ) -> Dict[str, PromptTemplateEntry]:
        prompts = {
            self.FREEFORM_SOLVE_FREE_PROMPT_ID: (
                self.FREEFORM_SOLVE_FREE_PROMPT_ASSET,
                PromptTierEnum.FREE,
            ),
            self.FREEFORM_SOLVE_PROMPT_ID: (
                self.FREEFORM_SOLVE_PROMPT_ASSET,
                PromptTierEnum.STANDARD,
            ),
            self.FREEFORM_SOLVE_RESEARCH_PROMPT_ID: (
                self.FREEFORM_SOLVE_RESEARCH_PROMPT_ASSET,
                PromptTierEnum.RESEARCH,
            ),
        }
        created: Dict[str, PromptTemplateEntry] = {}
        for prompt_id, (asset_path, tier_enum) in prompts.items():
            content = self._load_asset_text(asset_path)
            if "{PROBLEM}" not in content:
                raise PromptRegistryError(f"Prompt {prompt_id} missing required placeholder {{PROBLEM}}")
            created[prompt_id] = self._upsert_prompt_if_checksum_differs(
                session=session,
                prompt_id=prompt_id,
                content=content,
                tier=tier_enum,
                mode=PromptModeEnum.SOLVE,
                role=PromptRoleEnum.DEVELOPER,
                updated_by=updated_by,
            )
        return created

    def get_active_freeform_prompt_for_tier(
        self,
        session: Session,
        tier: PromptTierEnum,
        provider: str,
        model: str,
        mode: PromptModeEnum = PromptModeEnum.SOLVE,
    ) -> Optional[PromptTemplateEntry]:
        if (provider or "").strip().lower() != "openai":
            return None
        prompt_id = self.FREEFORM_SOLVE_TIER_PROMPT_IDS.get(tier)
        if not prompt_id:
            return None
        entry = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == prompt_id)
            .where(PromptTemplateEntry.tier == tier)
            .where(PromptTemplateEntry.mode == mode)
            .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
        ).first()
        return entry

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

    def audit_active_bindings(self, session: Session) -> Dict[str, Any]:
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

        expected_pairs = {(tier.value, mode.value) for tier in PromptTierEnum for mode in PromptModeEnum}
        found_pairs = set(key_latest.keys())
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
        normalized = self.normalize_schema_content(schema_content)
        try:
            Draft202012Validator.check_schema(normalized)
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
        normalized_content = self.normalize_schema_content(content)
        current = self.get_active_schema(session, schema_id)
        if current and json.dumps(current.content, sort_keys=True) == json.dumps(normalized_content, sort_keys=True):
            return current

        versions = self.get_schema_versions(session, schema_id)
        max_version = max((entry.version for entry in versions), default=0)
        next_version = self._next_version(max_version)
        if current:
            current.is_active = False
            current.updated_at = datetime.utcnow()

        entry = JsonSchemaEntry(
            schema_id=schema_id,
            content=normalized_content,
            version=next_version,
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    def normalize_schema_content(self, schema_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept either raw JSON Schema or OpenAI response_format wrappers and
        normalize to a plain JSON Schema object.
        """
        if not isinstance(schema_content, dict):
            return schema_content

        # OpenAI wrapper style: {"type":"json_schema","schema":{...}}
        if schema_content.get("type") == "json_schema" and isinstance(schema_content.get("schema"), dict):
            return schema_content["schema"]

        # OpenAI wrapper style: {"type":"json_schema","json_schema":{"schema":{...}}}
        json_schema_block = schema_content.get("json_schema")
        if schema_content.get("type") == "json_schema" and isinstance(json_schema_block, dict):
            if isinstance(json_schema_block.get("schema"), dict):
                return json_schema_block["schema"]
            return json_schema_block

        # Wrapper style without explicit `type`: {"name": "...", "schema": {...}, "strict": true}
        wrapper_keys = {"name", "schema", "strict", "description"}
        if isinstance(schema_content.get("schema"), dict) and set(schema_content.keys()).issubset(wrapper_keys):
            return schema_content["schema"]

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
            is_active=True,
            updated_by=updated_by,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


prompt_registry_service = PromptRegistryService()
