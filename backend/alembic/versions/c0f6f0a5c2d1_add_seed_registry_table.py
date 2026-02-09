"""add_seed_registry_table

Revision ID: c0f6f0a5c2d1
Revises: e39acf3d7451
Create Date: 2026-02-09 13:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c0f6f0a5c2d1"
down_revision: Union[str, None] = "e39acf3d7451"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seed_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seed_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("seed_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("git_sha", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("environment", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("checksum", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_seed_registry_seed_name"), "seed_registry", ["seed_name"], unique=True)
    op.create_index(op.f("ix_seed_registry_environment"), "seed_registry", ["environment"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_seed_registry_environment"), table_name="seed_registry")
    op.drop_index(op.f("ix_seed_registry_seed_name"), table_name="seed_registry")
    op.drop_table("seed_registry")
