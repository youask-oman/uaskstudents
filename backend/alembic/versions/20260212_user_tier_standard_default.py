"""set all users subscription_tier to standard

Revision ID: 20260212_user_tier_std
Revises: 20260212_prompt_binding_pricing
Create Date: 2026-02-12 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260212_user_tier_std"
down_revision: Union[str, Sequence[str], None] = "20260212_prompt_binding_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE \"user\" SET subscription_tier = 'standard';")


def downgrade() -> None:
    op.execute("UPDATE \"user\" SET subscription_tier = 'free' WHERE subscription_tier = 'standard';")
