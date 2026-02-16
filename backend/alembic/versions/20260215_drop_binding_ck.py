"""Drop hard-coded prompt_bindings allowlist check

Revision ID: 20260215_drop_binding_ck
Revises: 20260215_drop_schema_ck
Create Date: 2026-02-15
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260215_drop_binding_ck"
down_revision: Union[str, None] = "20260215_drop_schema_ck"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompt_bindings DROP CONSTRAINT IF EXISTS ck_prompt_bindings_solve_only_allowed")


def downgrade() -> None:
    op.execute("ALTER TABLE prompt_bindings DROP CONSTRAINT IF EXISTS ck_prompt_bindings_solve_only_allowed")
    op.execute(
        """
        ALTER TABLE prompt_bindings
        ADD CONSTRAINT ck_prompt_bindings_solve_only_allowed
        CHECK (
            mode = 'SOLVE' AND
            tier IN ('SHORT', 'FREE', 'STANDARD', 'RESEARCH') AND
            global_system_prompt_id = 'global_system_prompt_batch_v1' AND
            developer_prompt_id IN (
                'solve_dev_final_v2',
                'solve_dev_free_v2',
                'solve_dev_standard_v2',
                'solve_dev_research_v2'
            ) AND
            output_schema_id IN (
                'solve_batch_final_v2',
                'solve_batch_free_v2',
                'solve_batch_standard_v2',
                'solve_batch_research_v2'
            )
        )
        """
    )
