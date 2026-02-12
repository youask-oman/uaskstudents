from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlmodel import Session, select

from app.models import CreditLot, CreditTransfer, Notification, SystemConfig, User
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.credit_transfer_service import CreditTransferError, credit_transfer_service
from app.services.notification_service import notification_service


def _mk_user(session: Session, email_prefix: str) -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"{email_prefix}_{suffix}@example.com",
        full_name=f"{email_prefix} user",
        password_hash="x",
        is_verified=True,
    )
    session.add(user)
    session.flush()
    return user


def _set_transfer_flags(session: Session) -> None:
    pairs = {
        "CREDIT_TRANSFER_ENABLED": "true",
        "NOTIFICATIONS_ENABLED": "true",
        "CREDIT_TRANSFER_MIN": "1",
        "CREDIT_TRANSFER_MAX": "1000",
        "CREDIT_TRANSFER_DAILY_CAP": "5000",
        "CREDIT_TRANSFER_PENDING_EXPIRY_DAYS": "30",
        "CREDIT_TRANSFER_PER_MIN_LIMIT": "50",
        "NOTIFICATIONS_THANK_PER_MIN_LIMIT": "10",
        "CREDIT_TRANSFER_ACCOUNT_AGE_MINUTES": "0",
    }
    for key, val in pairs.items():
        row = session.get(SystemConfig, key)
        if row:
            row.value = val
        else:
            row = SystemConfig(key=key, value=val)
            session.add(row)
    session.flush()


def _seed_sender_lot(session: Session, sender_id: int, amount: Decimal = Decimal("100")) -> CreditLot:
    lot = CreditLot(
        user_id=sender_id,
        credits_total=amount,
        credits_remaining=amount,
        lot_type="TOPUP",
        status="ACTIVE",
        source="TEST",
    )
    session.add(lot)
    session.flush()
    return lot


def test_notification_dedupe_and_read_flow(session: Session):
    user = _mk_user(session, "notif")
    first = notification_service.create_notification(
        session,
        user_id=user.id,
        type="TEST",
        title="Hello",
        body="World",
        dedupe_key=f"notif:{user.id}:1",
    )
    second = notification_service.create_notification(
        session,
        user_id=user.id,
        type="TEST",
        title="Hello",
        body="World",
        dedupe_key=f"notif:{user.id}:1",
    )
    assert first.id == second.id

    row = notification_service.mark_read(session, user_id=user.id, notification_id=first.id)
    assert row is not None
    assert row.is_read is True

    updated = notification_service.mark_all_read(session, user_id=user.id)
    assert updated >= 0


def test_transfer_completed_existing_recipient(session: Session):
    _set_transfer_flags(session)
    sender = _mk_user(session, "sender")
    recipient = _mk_user(session, "recipient")
    _seed_sender_lot(session, sender.id, Decimal("120"))

    cfg = load_credit_transfer_config(session)
    transfer = credit_transfer_service.create_transfer(
        session,
        sender=sender,
        recipient_email_raw=recipient.email,
        amount=Decimal("25"),
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        cfg=cfg,
        sender_ip="127.0.0.1",
    )
    session.commit()

    session.refresh(transfer)
    assert transfer.status == "COMPLETED"
    assert transfer.recipient_user_id == recipient.id

    recipient_lot = session.exec(
        select(CreditLot)
        .where(CreditLot.user_id == recipient.id)
        .where(CreditLot.external_ref == transfer.id)
    ).first()
    assert recipient_lot is not None
    assert recipient_lot.status == "ACTIVE"


def test_transfer_pending_then_claim(session: Session):
    _set_transfer_flags(session)
    sender = _mk_user(session, "sender_pending")
    _seed_sender_lot(session, sender.id, Decimal("80"))

    pending_email = f"pending_{uuid.uuid4().hex[:8]}@example.com"
    cfg = load_credit_transfer_config(session)
    transfer = credit_transfer_service.create_transfer(
        session,
        sender=sender,
        recipient_email_raw=pending_email,
        amount=Decimal("15"),
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        cfg=cfg,
    )
    assert transfer.status == "PENDING"

    recipient = User(email=pending_email, full_name="Pending Recipient", password_hash="x", is_verified=True)
    session.add(recipient)
    session.flush()

    claimed = credit_transfer_service.claim_pending_for_user(session, recipient)
    session.commit()

    assert len(claimed) == 1
    session.refresh(transfer)
    assert transfer.status == "COMPLETED"
    assert transfer.recipient_user_id == recipient.id


def test_transfer_idempotency_no_double_debit(session: Session):
    _set_transfer_flags(session)
    sender = _mk_user(session, "sender_idem")
    recipient = _mk_user(session, "recipient_idem")
    _seed_sender_lot(session, sender.id, Decimal("60"))

    cfg = load_credit_transfer_config(session)
    idem = f"idem-{uuid.uuid4().hex}"
    t1 = credit_transfer_service.create_transfer(
        session,
        sender=sender,
        recipient_email_raw=recipient.email,
        amount=Decimal("10"),
        idempotency_key=idem,
        cfg=cfg,
    )
    t2 = credit_transfer_service.create_transfer(
        session,
        sender=sender,
        recipient_email_raw=recipient.email,
        amount=Decimal("10"),
        idempotency_key=idem,
        cfg=cfg,
    )
    session.commit()

    assert t1.id == t2.id
    count = session.exec(
        select(CreditTransfer)
        .where(CreditTransfer.sender_user_id == sender.id)
        .where(CreditTransfer.idempotency_key == idem)
    ).all()
    assert len(count) == 1


def test_self_transfer_blocked(session: Session):
    _set_transfer_flags(session)
    sender = _mk_user(session, "self")
    _seed_sender_lot(session, sender.id, Decimal("40"))
    cfg = load_credit_transfer_config(session)

    with pytest.raises(CreditTransferError) as exc:
        credit_transfer_service.create_transfer(
            session,
            sender=sender,
            recipient_email_raw=sender.email,
            amount=Decimal("5"),
            idempotency_key=f"idem-{uuid.uuid4().hex}",
            cfg=cfg,
        )

    assert exc.value.code == "self_transfer"


def test_expiry_refund_marks_transfer_refunded(session: Session):
    _set_transfer_flags(session)
    sender = _mk_user(session, "refund_sender")
    _seed_sender_lot(session, sender.id, Decimal("40"))
    cfg = load_credit_transfer_config(session)
    transfer = credit_transfer_service.create_transfer(
        session,
        sender=sender,
        recipient_email_raw=f"x_{uuid.uuid4().hex[:8]}@example.com",
        amount=Decimal("7"),
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        cfg=cfg,
    )

    transfer.expires_at = datetime.utcnow() - timedelta(minutes=1)
    session.add(transfer)
    session.flush()

    refunded = credit_transfer_service.expire_and_refund_pending(session)
    session.commit()
    assert any(t.id == transfer.id for t in refunded)
    session.refresh(transfer)
    assert transfer.status == "REFUNDED"

