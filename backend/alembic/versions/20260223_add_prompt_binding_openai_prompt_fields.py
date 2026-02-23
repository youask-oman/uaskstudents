"""add dedicated OpenAI managed prompt fields to prompt_bindings

Revision ID: 20260223_pb_openai_prompt_fields
Revises: 20260222_add_solve_debug_blob
Create Date: 2026-02-23 03:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260223_pb_openai_prompt_fields"
down_revision = "20260222_add_solve_debug_blob"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prompt_bindings", sa.Column("openai_prompt_id", sa.String(), nullable=True))
    op.add_column("prompt_bindings", sa.Column("openai_prompt_version", sa.String(), nullable=True))
    op.add_column(
        "prompt_bindings",
        sa.Column("openai_prompt_use_latest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("prompt_bindings", sa.Column("openai_prompt_variable_mapping", sa.JSON(), nullable=True))
    op.create_index("ix_prompt_bindings_openai_prompt_id", "prompt_bindings", ["openai_prompt_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_prompt_bindings_openai_prompt_id", table_name="prompt_bindings")
    op.drop_column("prompt_bindings", "openai_prompt_variable_mapping")
    op.drop_column("prompt_bindings", "openai_prompt_use_latest")
    op.drop_column("prompt_bindings", "openai_prompt_version")
    op.drop_column("prompt_bindings", "openai_prompt_id")
