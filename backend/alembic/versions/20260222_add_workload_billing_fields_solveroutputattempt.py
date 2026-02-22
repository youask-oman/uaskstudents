"""add workload billing fields to solveroutputattempt

Revision ID: 20260222_workload_billing1
Revises: 20260221_restore_schema_contract
Create Date: 2026-02-22 09:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_workload_billing1"
down_revision = "20260221_restore_schema_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("solveroutputattempt", sa.Column("billing_breakdown_json", sa.JSON(), nullable=True))
    op.add_column("solveroutputattempt", sa.Column("solve_mode", sa.String(), nullable=True))
    op.add_column("solveroutputattempt", sa.Column("charged_total_credits", sa.Numeric(20, 10), nullable=True))
    op.add_column("solveroutputattempt", sa.Column("selected_task_ids_json", sa.JSON(), nullable=True))
    op.create_index("ix_solveroutputattempt_solve_mode", "solveroutputattempt", ["solve_mode"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_solveroutputattempt_solve_mode", table_name="solveroutputattempt")
    op.drop_column("solveroutputattempt", "selected_task_ids_json")
    op.drop_column("solveroutputattempt", "charged_total_credits")
    op.drop_column("solveroutputattempt", "solve_mode")
    op.drop_column("solveroutputattempt", "billing_breakdown_json")
