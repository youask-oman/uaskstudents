"""add prompt binding pricing/features and backfill from plan

Revision ID: 20260212_prompt_binding_pricing
Revises: 20260211_legal_acceptances, f63fb794a9ff
Create Date: 2026-02-12 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260212_prompt_binding_pricing"
down_revision: Union[str, Sequence[str], None] = ("20260211_legal_acceptances", "f63fb794a9ff")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_for_tier(tier: str, primary_slug: str, fallback_slug: Union[str, None] = None) -> None:
    fallback_features_sql = (
        f"(SELECT p.features FROM plan p WHERE p.slug = '{fallback_slug}' ORDER BY p.id DESC LIMIT 1)"
        if fallback_slug
        else "NULL"
    )
    fallback_multipliers_sql = (
        f"(SELECT p.multipliers FROM plan p WHERE p.slug = '{fallback_slug}' ORDER BY p.id DESC LIMIT 1)"
        if fallback_slug
        else "NULL"
    )

    op.execute(
        f"""
        UPDATE prompt_bindings pb
        SET
          features = COALESCE(
            NULLIF(pb.features::text, '{{}}')::json,
            (SELECT p.features FROM plan p WHERE p.slug = '{primary_slug}' ORDER BY p.id DESC LIMIT 1),
            {fallback_features_sql},
            '{{}}'::json
          ),
          multipliers = COALESCE(
            NULLIF(pb.multipliers::text, '{{}}')::json,
            (SELECT p.multipliers FROM plan p WHERE p.slug = '{primary_slug}' ORDER BY p.id DESC LIMIT 1),
            {fallback_multipliers_sql},
            '{{}}'::json
          )
        WHERE pb.tier = '{tier}';
        """
    )


def upgrade() -> None:
    op.add_column("prompt_bindings", sa.Column("features", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("prompt_bindings", sa.Column("multipliers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    _backfill_for_tier("FREE", "free")
    _backfill_for_tier("SHORT", "family_standard")
    _backfill_for_tier("STANDARD", "standard", fallback_slug="student_standard")
    _backfill_for_tier("RESEARCH", "research")


def downgrade() -> None:
    op.drop_column("prompt_bindings", "multipliers")
    op.drop_column("prompt_bindings", "features")
