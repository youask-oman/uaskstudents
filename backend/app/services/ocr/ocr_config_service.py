from typing import Tuple, Optional
from sqlmodel import Session

from app.models import PromptTemplateEntry, JsonSchemaEntry
from app.services.prompt_registry_service import prompt_registry_service, PromptRegistryError
from app.services.ocr.ocr_runtime_config_service import (
    get_active_ocr_config,
    resolve_prompt_entry,
    resolve_schema_entry,
)


OPENAI_OCR_PROMPT_KEY = "openai_ocr_system_prompt_v1"
OPENAI_OCR_SCHEMA_KEY = "openai_image_extract_v1"
OPENAI_OCR_PROMPT_FALLBACK = "openai_ocr_system_prompt_v1.txt"
OPENAI_OCR_SCHEMA_FALLBACK = "openai_image_extract_v1.schema.json"


class OcrConfigService:
    """
    DB-driven OCR prompt/schema lookup.
    Avoids .env-driven IDs to keep prompts/schemas versionable via DB.
    """

    def get_openai_ocr_assets(
        self,
        session: Session,
        prompt_key: Optional[str] = None,
        schema_key: Optional[str] = None,
    ) -> Tuple[PromptTemplateEntry, JsonSchemaEntry]:
        runtime_cfg = get_active_ocr_config(session)
        prompt_id = prompt_key or runtime_cfg.openai_system_prompt_key or OPENAI_OCR_PROMPT_FALLBACK
        schema_id = schema_key or runtime_cfg.openai_schema_key or OPENAI_OCR_SCHEMA_FALLBACK

        prompt_entry = resolve_prompt_entry(session, prompt_id)
        if not prompt_entry:
            prompt_entry = prompt_registry_service.get_active_prompt(session, OPENAI_OCR_PROMPT_KEY)
        if not prompt_entry:
            prompt_entry = prompt_registry_service.get_active_prompt(session, OPENAI_OCR_PROMPT_FALLBACK)

        schema_entry = resolve_schema_entry(session, schema_id)
        if not schema_entry:
            schema_entry = prompt_registry_service.get_active_schema(session, OPENAI_OCR_SCHEMA_KEY)
        if not schema_entry:
            schema_entry = prompt_registry_service.get_active_schema(session, OPENAI_OCR_SCHEMA_FALLBACK)

        if not prompt_entry or not schema_entry:
            raise PromptRegistryError(
                f"Missing OCR prompt/schema in DB. Expected prompt_id={prompt_id} schema_id={schema_id}"
            )
        return prompt_entry, schema_entry


ocr_config_service = OcrConfigService()
