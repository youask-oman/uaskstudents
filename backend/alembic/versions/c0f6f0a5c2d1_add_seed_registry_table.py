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
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS seed_registry (
            id SERIAL PRIMARY KEY,
            seed_name VARCHAR NOT NULL,
            seed_version INTEGER DEFAULT 1 NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            git_sha VARCHAR,
            environment VARCHAR NOT NULL,
            row_count INTEGER,
            checksum VARCHAR,
            notes VARCHAR
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_seed_registry_seed_name ON seed_registry (seed_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_registry_environment ON seed_registry (environment)")


def downgrade() -> None:
    op.drop_index(op.f("ix_seed_registry_environment"), table_name="seed_registry")
    op.drop_index(op.f("ix_seed_registry_seed_name"), table_name="seed_registry")
    op.drop_table("seed_registry")
