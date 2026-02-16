"""Drop hard-coded json_schemas allowlist check

Revision ID: 20260215_drop_schema_ck
Revises: 20260215_ocr_registry_restore
Create Date: 2026-02-15
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260215_drop_schema_ck"
down_revision: Union[str, None] = "20260215_ocr_registry_restore"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE json_schemas DROP CONSTRAINT IF EXISTS ck_json_schemas_allowed_ids")


def downgrade() -> None:
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
