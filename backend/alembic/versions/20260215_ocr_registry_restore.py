"""Restore OCR prompt/schema IDs in registry and seed missing OCR assets.

Revision ID: 20260215_ocr_registry_restore
Revises: 20260215_credit_bill_seed
Create Date: 2026-02-15
"""

from typing import Sequence, Union
from uuid import uuid4
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260215_ocr_registry_restore"
down_revision: Union[str, None] = "20260215_credit_bill_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OCR_PROMPT_CONTENT = (
    "You are an OCR extraction engine for math content.\n"
    "Read the uploaded image and return JSON only.\n"
    "Extract clear question text, latex when present, and answer choices when present.\n"
    "Do not invent text not visible in the image.\n"
)

OCR_SCHEMA_CONTENT = {
    "name": "openai_image_extract_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "request_id": {"type": ["string", "null"]},
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "questions": {
                "type": "array",
                "default": [],
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "question_id": {"type": "string"},
                        "page_index": {"type": "integer", "minimum": 0},
                        "question_text": {"type": "string"},
                        "question_latex": {"type": ["string", "null"]},
                        "answer_choices": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "confidence": {"type": ["number", "null"]},
                        "subparts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": ["question_id", "page_index", "question_text"],
                },
            },
        },
        "required": ["questions"],
    },
}


def _upsert_prompt(bind: sa.engine.Connection, prompt_id: str, updated_by: str) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO prompt_templates
                (id, prompt_id, tier, mode, role, content, version, is_active, created_at, updated_at, updated_by)
            VALUES
                (:id, :prompt_id, NULL, :mode, :role, :content, 1, true, NOW(), NOW(), :updated_by)
            ON CONFLICT (prompt_id, version)
            DO UPDATE SET
                content = EXCLUDED.content,
                is_active = true,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            """
        ),
        {
            "id": str(uuid4()),
            "prompt_id": prompt_id,
            "mode": "OCR_EXTRACT",
            "role": "SYSTEM",
            "content": OCR_PROMPT_CONTENT,
            "updated_by": updated_by,
        },
    )


def _upsert_schema(bind: sa.engine.Connection, schema_id: str, updated_by: str) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO json_schemas
                (id, schema_id, content, version, is_active, created_at, updated_at, updated_by)
            VALUES
                (:id, :schema_id, CAST(:content AS JSON), 1, true, NOW(), NOW(), :updated_by)
            ON CONFLICT (schema_id, version)
            DO UPDATE SET
                content = EXCLUDED.content,
                is_active = true,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            """
        ),
        {
            "id": str(uuid4()),
            "schema_id": schema_id,
            "content": json.dumps(OCR_SCHEMA_CONTENT, ensure_ascii=False),
            "updated_by": updated_by,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    updated_by = f"alembic:{revision}"

    op.execute("ALTER TABLE prompt_templates DROP CONSTRAINT IF EXISTS ck_prompt_templates_allowed_ids")
    op.execute(
        """
        ALTER TABLE prompt_templates
        ADD CONSTRAINT ck_prompt_templates_allowed_ids
        CHECK (
            prompt_id IN (
                'global_system_prompt_batch_v1',
                'solve_dev_final_v2',
                'solve_dev_free_v2',
                'solve_dev_standard_v2',
                'solve_dev_research_v2',
                'openai_ocr_system_prompt_v1',
                'openai_ocr_system_prompt_v1.txt'
            )
        )
        """
    )

    op.execute("ALTER TABLE json_schemas DROP CONSTRAINT IF EXISTS ck_json_schemas_allowed_ids")
    op.execute(
        """
        ALTER TABLE json_schemas
        ADD CONSTRAINT ck_json_schemas_allowed_ids
        CHECK (
            schema_id IN (
                'solve_batch_final_v2',
                'solve_batch_free_v2',
                'solve_batch_standard_v2',
                'solve_batch_research_v2',
                'openai_image_extract_v1',
                'openai_image_extract_v1.schema.json',
                'openai_image_extract_v1_schema_json'
            )
        )
        """
    )

    _upsert_prompt(bind, "openai_ocr_system_prompt_v1", updated_by)
    _upsert_prompt(bind, "openai_ocr_system_prompt_v1.txt", updated_by)
    _upsert_schema(bind, "openai_image_extract_v1", updated_by)
    _upsert_schema(bind, "openai_image_extract_v1.schema.json", updated_by)
    _upsert_schema(bind, "openai_image_extract_v1_schema_json", updated_by)


def downgrade() -> None:
    op.execute("DELETE FROM prompt_templates WHERE prompt_id IN ('openai_ocr_system_prompt_v1', 'openai_ocr_system_prompt_v1.txt')")
    op.execute(
        "DELETE FROM json_schemas WHERE schema_id IN "
        "('openai_image_extract_v1', 'openai_image_extract_v1.schema.json', 'openai_image_extract_v1_schema_json')"
    )

    op.execute("ALTER TABLE prompt_templates DROP CONSTRAINT IF EXISTS ck_prompt_templates_allowed_ids")
    op.execute(
        """
        ALTER TABLE prompt_templates
        ADD CONSTRAINT ck_prompt_templates_allowed_ids
        CHECK (
            prompt_id IN (
                'global_system_prompt_batch_v1',
                'solve_dev_final_v2',
                'solve_dev_free_v2',
                'solve_dev_standard_v2',
                'solve_dev_research_v2'
            )
        )
        """
    )

    op.execute("ALTER TABLE json_schemas DROP CONSTRAINT IF EXISTS ck_json_schemas_allowed_ids")
    op.execute(
        """
        ALTER TABLE json_schemas
        ADD CONSTRAINT ck_json_schemas_allowed_ids
        CHECK (
            schema_id IN (
                'solve_batch_final_v2',
                'solve_batch_free_v2',
                'solve_batch_standard_v2',
                'solve_batch_research_v2'
            )
        )
        """
    )
