"""add chat edit v2 tables

Revision ID: 77c7a9c0f3b1
Revises: 6f4c2fbb8d1e
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "77c7a9c0f3b1"
down_revision = "6f4c2fbb8d1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chateditnotev2",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chatsession.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("notes_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_edit_note_v2_chat_user"),
    )
    op.create_index("ix_chat_edit_note_v2_chat_user", "chateditnotev2", ["chat_id", "user_id"], unique=False)

    op.create_table(
        "chateditcopyv2",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chatsession.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("edited_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_md_hash", sa.String(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_edit_copy_v2_chat_user"),
    )
    op.create_index("ix_chat_edit_copy_v2_chat_user", "chateditcopyv2", ["chat_id", "user_id"], unique=False)
    op.create_index("ix_chateditcopyv2_canonical_md_hash", "chateditcopyv2", ["canonical_md_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chateditcopyv2_canonical_md_hash", table_name="chateditcopyv2")
    op.drop_index("ix_chat_edit_copy_v2_chat_user", table_name="chateditcopyv2")
    op.drop_table("chateditcopyv2")
    op.drop_index("ix_chat_edit_note_v2_chat_user", table_name="chateditnotev2")
    op.drop_table("chateditnotev2")
