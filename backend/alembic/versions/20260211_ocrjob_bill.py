"""Add OCR job billing fields

Revision ID: 20260211_ocrjob_bill
Revises: 1bff2dc3dfd0
Create Date: 2026-02-11 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260211_ocrjob_bill"
down_revision: Union[str, None] = "1bff2dc3dfd0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS extracted_text TEXT")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS structured_json JSON")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS image_fingerprint VARCHAR")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS prompt_template_id VARCHAR")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS json_schema_id VARCHAR")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS hold_request_id VARCHAR")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS hold_amount NUMERIC(20, 10)")
    op.execute("ALTER TABLE ocrjob ADD COLUMN IF NOT EXISTS accepted_solve_attempt_id VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ocrjob_user_dedupe ON ocrjob (user_id, dedupe_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ocrjob_user_created ON ocrjob (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ocrjob_image_fingerprint ON ocrjob (image_fingerprint)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ocrjob_image_fingerprint")
    op.execute("DROP INDEX IF EXISTS ix_ocrjob_user_created")
    op.execute("DROP INDEX IF EXISTS ix_ocrjob_user_dedupe")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS accepted_solve_attempt_id")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS hold_amount")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS hold_request_id")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS json_schema_id")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS prompt_template_id")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS dedupe_key")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS image_fingerprint")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS quality_score")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS structured_json")
    op.execute("ALTER TABLE ocrjob DROP COLUMN IF EXISTS extracted_text")
