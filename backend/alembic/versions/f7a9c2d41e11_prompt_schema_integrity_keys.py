"""Prompt/schema integrity keys and active binding uniqueness.

Revision ID: f7a9c2d41e11
Revises: c0f6f0a5c2d1
Create Date: 2026-02-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a9c2d41e11"
down_revision: Union[str, None] = "c0f6f0a5c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_template_keys",
        sa.Column("prompt_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("prompt_id"),
    )
    op.create_table(
        "json_schema_keys",
        sa.Column("schema_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("schema_id"),
    )

    op.execute(
        """
        INSERT INTO prompt_template_keys(prompt_id)
        SELECT DISTINCT prompt_id
        FROM prompt_templates
        WHERE prompt_id IS NOT NULL
        ON CONFLICT (prompt_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO json_schema_keys(schema_id)
        SELECT DISTINCT schema_id
        FROM json_schemas
        WHERE schema_id IS NOT NULL
        ON CONFLICT (schema_id) DO NOTHING
        """
    )

    op.create_foreign_key(
        "fk_prompt_bindings_global_system_prompt_key",
        "prompt_bindings",
        "prompt_template_keys",
        ["global_system_prompt_id"],
        ["prompt_id"],
    )
    op.create_foreign_key(
        "fk_prompt_bindings_developer_prompt_key",
        "prompt_bindings",
        "prompt_template_keys",
        ["developer_prompt_id"],
        ["prompt_id"],
    )
    op.create_foreign_key(
        "fk_prompt_bindings_output_schema_key",
        "prompt_bindings",
        "json_schema_keys",
        ["output_schema_id"],
        ["schema_id"],
    )

    op.create_index(
        "uq_prompt_bindings_active_tier_mode",
        "prompt_bindings",
        ["tier", "mode"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_prompt_bindings_active_tier_mode", table_name="prompt_bindings")
    op.drop_constraint("fk_prompt_bindings_output_schema_key", "prompt_bindings", type_="foreignkey")
    op.drop_constraint("fk_prompt_bindings_developer_prompt_key", "prompt_bindings", type_="foreignkey")
    op.drop_constraint("fk_prompt_bindings_global_system_prompt_key", "prompt_bindings", type_="foreignkey")
    op.drop_table("json_schema_keys")
    op.drop_table("prompt_template_keys")
