"""add_solution_shares_table

Revision ID: 20260213_solution_shares
Revises: 20260212_credit_transfer_notif
Create Date: 2026-02-13 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260213_solution_shares"
down_revision: Union[str, Sequence[str], None] = "20260212_credit_transfer_notif"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS solution_shares (
            id VARCHAR PRIMARY KEY,
            solver_output_attempt_id INTEGER NOT NULL REFERENCES solveroutputattempt (id) ON DELETE CASCADE,
            attempt_id VARCHAR NOT NULL,
            owner_user_id INTEGER NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
            visibility VARCHAR NOT NULL DEFAULT 'PRIVATE',
            share_token VARCHAR NULL,
            share_token_hash VARCHAR NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            revoked_at TIMESTAMP WITHOUT TIME ZONE NULL,
            last_viewed_at TIMESTAMP WITHOUT TIME ZONE NULL,
            view_count INTEGER NOT NULL DEFAULT 0,
            expires_at TIMESTAMP WITHOUT TIME ZONE NULL,
            metadata_json JSON NULL
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_solution_share_owner_attempt ON solution_shares (owner_user_id, attempt_id)"
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_solution_share_token ON solution_shares (share_token)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_solution_share_token_hash ON solution_shares (share_token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_solution_share_attempt_owner ON solution_shares (attempt_id, owner_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_solution_shares_visibility ON solution_shares (visibility)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_solution_shares_revoked_at ON solution_shares (revoked_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_solution_shares_expires_at ON solution_shares (expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_solution_shares_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_solution_shares_revoked_at")
    op.execute("DROP INDEX IF EXISTS ix_solution_shares_visibility")
    op.execute("DROP INDEX IF EXISTS ix_solution_share_attempt_owner")
    op.execute("DROP INDEX IF EXISTS uq_solution_share_token_hash")
    op.execute("DROP INDEX IF EXISTS uq_solution_share_token")
    op.execute("DROP INDEX IF EXISTS uq_solution_share_owner_attempt")
    op.execute("DROP TABLE IF EXISTS solution_shares")
