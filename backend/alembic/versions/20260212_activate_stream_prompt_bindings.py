"""activate stream prompt bindings for solve and plot spec

Revision ID: 20260212_act_stream_bind
Revises: 20260212_solve_superset_v2
Create Date: 2026-02-12 23:58:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260212_act_stream_bind"
down_revision: Union[str, Sequence[str], None] = "20260212_solve_superset_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep one active binding per tier/mode for legacy stream resolver paths.
    op.execute(
        """
        UPDATE prompt_bindings
        SET is_active = CASE
            WHEN mode = 'SOLVE' THEN true
            WHEN mode = 'PLOT_SPEC' AND tier IN ('STANDARD', 'RESEARCH') THEN true
            ELSE is_active
        END,
        updated_at = NOW(),
        updated_by = 'alembic:20260212_activate_stream_bindings'
        WHERE mode IN ('SOLVE', 'PLOT_SPEC');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE prompt_bindings
        SET is_active = CASE
            WHEN mode IN ('SOLVE', 'PLOT_SPEC') THEN false
            ELSE is_active
        END,
        updated_at = NOW(),
        updated_by = 'alembic:20260212_activate_stream_bindings:down'
        WHERE mode IN ('SOLVE', 'PLOT_SPEC');
        """
    )
