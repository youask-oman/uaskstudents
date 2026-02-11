"""add legal_acceptances table

Revision ID: 20260211_legal_acceptances
Revises: 20260211_legal_documents
Create Date: 2026-02-11 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260211_legal_acceptances"
down_revision: Union[str, None] = "20260211_legal_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_acceptances (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            document_key VARCHAR(100) NOT NULL,
            document_version VARCHAR(32) NOT NULL,
            accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip VARCHAR(128) NULL,
            user_agent VARCHAR(1024) NULL,
            locale VARCHAR(64) NULL,
            method VARCHAR(32) NOT NULL DEFAULT 'in_app_modal',
            CONSTRAINT uq_legal_acceptances_user_doc_version
                UNIQUE (user_id, document_key, document_version)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_acceptances_user_doc_key_time "
        "ON legal_acceptances (user_id, document_key, accepted_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_acceptances_doc_key_version "
        "ON legal_acceptances (document_key, document_version)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_legal_acceptances_doc_key_version")
    op.execute("DROP INDEX IF EXISTS ix_legal_acceptances_user_doc_key_time")
    op.execute("DROP TABLE IF EXISTS legal_acceptances")
