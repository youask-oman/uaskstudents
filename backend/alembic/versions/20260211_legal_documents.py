"""add legal_documents table

Revision ID: 20260211_legal_documents
Revises: 20260211_ocrjob_bill
Create Date: 2026-02-11 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260211_legal_documents"
down_revision: Union[str, None] = "20260211_ocrjob_bill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_documents (
            id BIGSERIAL PRIMARY KEY,
            key VARCHAR(100) NOT NULL,
            version VARCHAR(32) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            content_md TEXT NOT NULL DEFAULT '',
            content_html TEXT NOT NULL DEFAULT '',
            effective_at TIMESTAMPTZ NULL,
            published_at TIMESTAMPTZ NULL,
            created_by BIGINT NULL,
            updated_by BIGINT NULL,
            checksum_sha256 VARCHAR(64) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_legal_documents_key_version UNIQUE (key, version)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_documents_key ON legal_documents (key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_documents_version ON legal_documents (version)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_documents_status ON legal_documents (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_documents_key_status ON legal_documents (key, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_documents_checksum_sha256 ON legal_documents (checksum_sha256)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_legal_documents_checksum_sha256")
    op.execute("DROP INDEX IF EXISTS ix_legal_documents_key_status")
    op.execute("DROP INDEX IF EXISTS ix_legal_documents_status")
    op.execute("DROP INDEX IF EXISTS ix_legal_documents_version")
    op.execute("DROP INDEX IF EXISTS ix_legal_documents_key")
    op.execute("DROP TABLE IF EXISTS legal_documents")
