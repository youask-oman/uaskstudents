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
    OCR_EXTRACT_QWEN_SYSTEM_PROMPT_ID = "ocr_extract_qwen_system_v1"
    OCR_EXTRACT_QWEN_USER_PROMPT_ID = "ocr_extract_qwen_user_v1"
    OCR_EXTRACT_OPENAI_SYSTEM_PROMPT_ID = "openai_ocr_system_prompt_v1"
    OCR_EXTRACT_OPENAI_SCHEMA_ID = "youask_math_solver_openai_ocr_v1"
    STANDARD_SOLVE_PROMPT_ID = "solve_standard_extreme_detailed_v1"
    STANDARD_SOLVE_SCHEMA_ID = "youask_math_solver_standard_solve_extreme_v1"
    STANDARD_SOLVE_GLOBAL_SYSTEM_ID = "global_system_prompt_v1"
    LEGACY_STANDARD_SOLVE_PROMPT_IDS = (
        "solve_standard_moderate_v1",
        "solve_standard_moderate_v2",
    )
    LEGACY_STANDARD_SOLVE_SCHEMA_IDS = (
        "youask_math_solver_standard_solve_v1",
        "youask_math_solver_standard_solve_v2",
    )

    OCR_EXTRACT_QWEN_SYSTEM_PROMPT_DEFAULT = (
        "You are a strict JSON extraction engine for math worksheets and textbook pages.\n"
        "Output ONLY valid JSON that matches the provided JSON schema exactly.\n"
        "Do not output markdown. Do not add commentary. Do not wrap in code fences.\n"
        "Do not include any keys not defined in the schema.\n"
        "Keys must have no leading or trailing whitespace.\n"
        "If you are uncertain about any field, use null where allowed and explain uncertainty in \"notes\".\n"
        "If the image/page is not a math page, set is_math_page=false and return questions=[] with ok=true."
    )
    OCR_EXTRACT_QWEN_USER_PROMPT_DEFAULT = (
        "Extract ALL math questions from the provided image or PDF page image(s).\n\n"
        "If there are multiple questions, split them into separate items in questions[].\n\n"
        "Preserve math notation. If you can express an equation in LaTeX confidently, put it in \"latex\"; otherwise set latex=null.\n\n"
        "Include page number for each question (0-based).\n\n"
        "If the page contains multiple subparts (a), (b), (c), either:\n"
        "(1) keep them in one question text, OR\n"
        "(2) create separate questions with ids p{page}-q{n}-part{letter}.\n"
        "Return JSON only."
    )
    STANDARD_SOLVE_PROMPT_ASSET = "backend/app/prompts/solve_standard_extreme_detailed_v1.txt"
    STANDARD_SOLVE_SCHEMA_ASSET = "backend/app/schemas/youask_math_solver_standard_solve_extreme_v1.json"

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _load_asset_text(self, rel_path: str) -> str:
        path = self._repo_root() / rel_path
        return path.read_text(encoding="utf-8").strip()

    def _load_asset_json(self, rel_path: str) -> Dict[str, Any]:
        path = self._repo_root() / rel_path
        return json.loads(path.read_text(encoding="utf-8"))

    def ensure_ocr_extract_prompts(self, session: Session, updated_by: Optional[str] = "system") -> None:
        """
        Ensure OCR Qwen post-processing prompts exist in prompt_templates.
        These IDs are read by runtime extraction flow and can be edited via registry admin APIs.
        """
        self._ensure_prompt_exists(
            session=session,
            prompt_id=self.OCR_EXTRACT_QWEN_SYSTEM_PROMPT_ID,
            content=self.OCR_EXTRACT_QWEN_SYSTEM_PROMPT_DEFAULT,
            tier=None,
            mode=PromptModeEnum.SOLVE,
            role=PromptRoleEnum.SYSTEM,
            updated_by=updated_by,
        )
        self._ensure_prompt_exists(
            session=session,
            prompt_id=self.OCR_EXTRACT_QWEN_USER_PROMPT_ID,
            content=self.OCR_EXTRACT_QWEN_USER_PROMPT_DEFAULT,
            tier=None,
            mode=PromptModeEnum.SOLVE,
            role=PromptRoleEnum.DEVELOPER,
            updated_by=updated_by,
        )
        openai_system_prompt = self._load_asset_text(
            "static_design/sug_prompts_qwen/openai_ocr_system_prompt_v1.txt"
        )
        openai_schema = self._load_asset_json(
            "static_design/sug_prompts_qwen/youask_math_solver_openai_ocr_v1.json"
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
