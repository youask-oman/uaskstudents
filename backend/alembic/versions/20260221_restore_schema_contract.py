"""restore schema contract by removing orphan debug blob table

Revision ID: 20260221_restore_schema_contract
Revises: 20260216_drop_prompt_ck
Create Date: 2026-02-21 15:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260221_restore_schema_contract"
down_revision = "20260216_drop_prompt_ck"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old contract does not include this table; drop if present.
    op.execute("DROP TABLE IF EXISTS solvedebugblob")


def downgrade() -> None:
    op.create_table(
        "solvedebugblob",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=False),
        sa.Column("blob_type", sa.String(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

