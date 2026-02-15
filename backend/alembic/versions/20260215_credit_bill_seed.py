"""credit_bill_seed placeholder

Revision ID: 20260215_credit_bill_seed
Revises: 20260213_solution_shares
Create Date: 2026-02-15 00:00:00.000000

This revision was previously used for seed-related changes. The runtime seed
pipeline now lives in scripts, so this migration is intentionally a no-op to
preserve Alembic graph integrity for existing databases stamped at this
revision.
"""

from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "20260215_credit_bill_seed"
down_revision: Union[str, Sequence[str], None] = "20260213_solution_shares"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
