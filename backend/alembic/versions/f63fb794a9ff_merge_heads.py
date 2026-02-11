"""merge heads

Revision ID: f63fb794a9ff
Revises: 20260211_ocrjob_bill, 77c7a9c0f3b1
Create Date: 2026-02-10 19:24:45.474608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f63fb794a9ff'
down_revision: Union[str, None] = ('20260211_ocrjob_bill', '77c7a9c0f3b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
