"""add math svg cache table

Revision ID: 20260212_math_svg_cache
Revises: 20260212_solve_v2_llm_min
Create Date: 2026-02-12 17:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260212_math_svg_cache"
down_revision: Union[str, Sequence[str], None] = "20260212_solve_v2_llm_min"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS math_svg_cache (
            key TEXT PRIMARY KEY,
            latex TEXT NOT NULL,
            config JSONB NOT NULL,
            svg_gzip BYTEA NOT NULL,
            metrics JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            hits BIGINT NOT NULL DEFAULT 0
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_math_svg_cache_last_accessed_at
        ON math_svg_cache (last_accessed_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_math_svg_cache_last_accessed_at;")
    op.execute("DROP TABLE IF EXISTS math_svg_cache;")

