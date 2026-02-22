"""add solve_debug_blob table for raw debug payload references

Revision ID: 20260222_add_solve_debug_blob
Revises: 20260222_workload_billing1
Create Date: 2026-02-22 10:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_add_solve_debug_blob"
down_revision = "20260222_workload_billing1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solve_debug_blob",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=False),
        sa.Column("blob_type", sa.String(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("stored_reason", sa.String(), nullable=False, server_default="debug"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_solve_debug_blob_attempt_id", "solve_debug_blob", ["attempt_id"], unique=False)
    op.create_index("ix_solve_debug_blob_blob_type", "solve_debug_blob", ["blob_type"], unique=False)
    op.create_index("ix_solve_debug_blob_sha256", "solve_debug_blob", ["sha256"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_solve_debug_blob_sha256", table_name="solve_debug_blob")
    op.drop_index("ix_solve_debug_blob_blob_type", table_name="solve_debug_blob")
    op.drop_index("ix_solve_debug_blob_attempt_id", table_name="solve_debug_blob")
    op.drop_table("solve_debug_blob")
