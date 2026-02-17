"""Drop hard-coded prompt_templates allowlist check.

Revision ID: 20260216_drop_prompt_ck
Revises: 20260215_rename_tiers
Create Date: 2026-02-16
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260216_drop_prompt_ck"
down_revision: Union[str, None] = "20260215_rename_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompt_templates DROP CONSTRAINT IF EXISTS ck_prompt_templates_allowed_ids")


def downgrade() -> None:
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
