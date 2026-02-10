"""Phase 2: Decimal + NUMERIC conversion for billing columns.

Revision ID: 2026020901_decimal_billing
Revises: 9cc1e47ff161
Create Date: 2026-02-09

This migration converts all float-based credit/money columns to NUMERIC(20,10)
for precise decimal arithmetic in financial operations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC


# revision identifiers, used by Alembic.
revision = '2026020901_decimal_billing'
down_revision = '9cc1e47ff161'
branch_labels = None
depends_on = None


def upgrade():
    """Convert float columns to NUMERIC(20, 10)."""
    
    # CreditLot
    op.alter_column('creditlot', 'credits_total',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_total::numeric(20,10)'
    )
    op.alter_column('creditlot', 'credits_remaining',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_remaining::numeric(20,10)'
    )
    op.alter_column('creditlot', 'amount_paid',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='amount_paid::numeric(20,10)'
    )
    
    # CreditLotConsumption
    op.alter_column('creditlotconsumption', 'amount',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='amount::numeric(20,10)'
    )
    
    # UsageLedger
    op.alter_column('usageledger', 'amount',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='amount::numeric(20,10)'
    )
    op.alter_column('usageledger', 'balance_after',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='balance_after::numeric(20,10)'
    )
    
    # Subscription
    op.alter_column('subscription', 'credits_balance',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_balance::numeric(20,10)'
    )
    op.alter_column('subscription', 'credits_used_this_period',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_used_this_period::numeric(20,10)'
    )
    
    # CreditHold
    op.alter_column('credithold', 'reserved_credits',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='reserved_credits::numeric(20,10)'
    )
    
    # BillingLedger
    op.alter_column('billingledger', 'credits_charged',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_charged::numeric(20,10)'
    )
    op.alter_column('billingledger', 'estimated_credits',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='estimated_credits::numeric(20,10)'
    )
    op.alter_column('billingledger', 'actual_credits',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='actual_credits::numeric(20,10)'
    )
    op.alter_column('billingledger', 'credits_before',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_before::numeric(20,10)'
    )
    op.alter_column('billingledger', 'credits_after',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credits_after::numeric(20,10)'
    )
    op.alter_column('billingledger', 'provider_cost_usd',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='provider_cost_usd::numeric(20,10)'
    )
    op.alter_column('billingledger', 'charge_usd',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='charge_usd::numeric(20,10)'
    )
    op.alter_column('billingledger', 'credit_value_usd',
        existing_type=sa.Float(),
        type_=NUMERIC(20, 10),
        existing_nullable=True,
        postgresql_using='credit_value_usd::numeric(20,10)'
    )
    
    # User cached balance
    # User cached balance - Column was missing in previous migration
    op.execute("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS credits_balance NUMERIC(20, 10) DEFAULT '0.0'")


def downgrade():
    """Revert NUMERIC columns back to Float (data loss possible)."""
    
    # User
    # User
    op.drop_column('user', 'credits_balance')
    
    # BillingLedger
    op.alter_column('billingledger', 'credit_value_usd',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'charge_usd',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'provider_cost_usd',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'credits_after',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'credits_before',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'actual_credits',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'estimated_credits',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('billingledger', 'credits_charged',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    
    # CreditHold
    op.alter_column('credithold', 'reserved_credits',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    
    # Subscription
    op.alter_column('subscription', 'credits_used_this_period',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('subscription', 'credits_balance',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    
    # UsageLedger
    op.alter_column('usageledger', 'balance_after',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('usageledger', 'amount',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    
    # CreditLotConsumption
    op.alter_column('creditlotconsumption', 'amount',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    
    # CreditLot
    op.alter_column('creditlot', 'amount_paid',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('creditlot', 'credits_remaining',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column('creditlot', 'credits_total',
        existing_type=NUMERIC(20, 10),
        type_=sa.Float(),
        existing_nullable=True
    )
