"""add prompt cache fields for OpenAI managed prompt on prompt_bindings

Revision ID: 20260223_pb_openai_prompt_cache
Revises: 20260223_pb_openai_prompt_fields
Create Date: 2026-02-23 06:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260223_pb_openai_prompt_cache"
down_revision = "20260223_pb_openai_prompt_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prompt_bindings", sa.Column("openai_prompt_cache_key_template", sa.String(), nullable=True))
    op.add_column("prompt_bindings", sa.Column("openai_prompt_cache_retention", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("prompt_bindings", "openai_prompt_cache_retention")
    op.drop_column("prompt_bindings", "openai_prompt_cache_key_template")

