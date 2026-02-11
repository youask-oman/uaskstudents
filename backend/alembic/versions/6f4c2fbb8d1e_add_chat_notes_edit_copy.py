"""add chat notes and edit copy tables

Revision ID: 6f4c2fbb8d1e
Revises: 7aa5b3a25e41
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "6f4c2fbb8d1e"
down_revision = "7aa5b3a25e41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatnote",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chatsession.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("notes_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_note_chat_user"),
    )
    op.create_index("ix_chat_note_chat_user", "chatnote", ["chat_id", "user_id"], unique=False)

    op.create_table(
        "chateditcopy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chatsession.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("edited_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_md_hash", sa.String(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_edit_copy_chat_user"),
    )
    op.create_index("ix_chat_edit_copy_chat_user", "chateditcopy", ["chat_id", "user_id"], unique=False)
    op.create_index("ix_chateditcopy_canonical_md_hash", "chateditcopy", ["canonical_md_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chateditcopy_canonical_md_hash", table_name="chateditcopy")
    op.drop_index("ix_chat_edit_copy_chat_user", table_name="chateditcopy")
    op.drop_table("chateditcopy")
    op.drop_index("ix_chat_note_chat_user", table_name="chatnote")
    op.drop_table("chatnote")
