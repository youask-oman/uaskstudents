"""add_notifications_and_credit_transfers

Revision ID: 20260212_credit_transfer_notif
Revises: 20260212_math_svg_cache
Create Date: 2026-02-12 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260212_credit_transfer_notif"
down_revision: Union[str, Sequence[str], None] = "20260212_math_svg_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_transfers (
            id VARCHAR PRIMARY KEY,
            sender_user_id INTEGER NOT NULL REFERENCES "user" (id),
            recipient_email VARCHAR NOT NULL,
            recipient_user_id INTEGER NULL REFERENCES "user" (id),
            amount NUMERIC(20,10) NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'PENDING',
            idempotency_key VARCHAR NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            claimed_at TIMESTAMP WITHOUT TIME ZONE NULL,
            failure_reason VARCHAR NULL,
            sender_ip_hash VARCHAR NULL,
            escrow_lot_id INTEGER NULL REFERENCES creditlot (id),
            sender_ledger_id INTEGER NULL REFERENCES billingledger (id),
            recipient_ledger_id INTEGER NULL REFERENCES billingledger (id),
            refund_ledger_id INTEGER NULL REFERENCES billingledger (id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_transfer_sender_idem ON credit_transfers (sender_user_id, idempotency_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_transfer_recipient_status ON credit_transfers (recipient_email, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_transfer_sender_created ON credit_transfers (sender_user_id, created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES "user" (id),
            type VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            body VARCHAR NOT NULL,
            payload_json JSON NULL,
            severity VARCHAR NOT NULL DEFAULT 'info',
            is_read BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            read_at TIMESTAMP WITHOUT TIME ZONE NULL,
            action_type VARCHAR NULL,
            action_payload JSON NULL,
            dedupe_key VARCHAR NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications (user_id, is_read)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_user_dedupe ON notifications (user_id, dedupe_key)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notifications_user_dedupe")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_unread")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_created")
    op.execute("DROP TABLE IF EXISTS notifications")

    op.execute("DROP INDEX IF EXISTS ix_credit_transfer_sender_created")
    op.execute("DROP INDEX IF EXISTS ix_credit_transfer_recipient_status")
    op.execute("DROP INDEX IF EXISTS uq_credit_transfer_sender_idem")
    op.execute("DROP TABLE IF EXISTS credit_transfers")

