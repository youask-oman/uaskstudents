from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlmodel import Session, select, func

from app.jobs.nightly_reconciliation import compute_user_balance
from app.models import BillingLedger, CreditLot, CreditTransfer, User
from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
from app.services.credit_transfer_config import CreditTransferConfig


@dataclass
class BalanceView:
    spendable_balance: Decimal
    pending_outgoing_total: Decimal
    can_transfer: bool
    min_transfer: Decimal
    max_transfer: Decimal
    daily_remaining: Decimal
    reason_if_disabled: Optional[str]
    credit_transfer_enabled: bool


class CreditTransferError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CreditTransferService:
    def _normalize_email(self, email: str) -> str:
        return (email or "").strip().lower()

    def _hash_ip(self, raw_ip: Optional[str]) -> Optional[str]:
        if not raw_ip:
            return None
        return hashlib.sha256(raw_ip.encode("utf-8")).hexdigest()

    def _recipient_user(self, session: Session, email: str) -> Optional[User]:
        return session.exec(select(User).where(User.email == email)).first()

    def _daily_sent(self, session: Session, sender_user_id: int, start: datetime) -> Decimal:
        total = session.exec(
            select(func.coalesce(func.sum(CreditTransfer.amount), 0))
            .where(CreditTransfer.sender_user_id == sender_user_id)
            .where(CreditTransfer.created_at >= start)
            .where(CreditTransfer.status.in_(["PENDING", "COMPLETED"]))
        ).one()
        return Decimal(str(total or 0))

    def _per_minute_count(self, session: Session, sender_user_id: int, since: datetime) -> int:
        return int(
            session.exec(
                select(func.count(CreditTransfer.id))
                .where(CreditTransfer.sender_user_id == sender_user_id)
                .where(CreditTransfer.created_at >= since)
            ).one()
            or 0
        )

    def _per_minute_ip_count(self, session: Session, sender_ip_hash: str, since: datetime) -> int:
        return int(
            session.exec(
                select(func.count(CreditTransfer.id))
                .where(CreditTransfer.sender_ip_hash == sender_ip_hash)
                .where(CreditTransfer.created_at >= since)
            ).one()
            or 0
        )

    def _validate_limits(
        self,
        *,
        sender: User,
        recipient_email: str,
        amount: Decimal,
        spendable: Decimal,
        cfg: CreditTransferConfig,
        daily_sent: Decimal,
        per_min_count: int,
    ) -> None:
        if not cfg.enabled:
            raise CreditTransferError("feature_disabled", "Credit transfer is disabled", 503)

        if amount <= 0:
            raise CreditTransferError("invalid_amount", "Amount must be greater than zero", 422)

        if amount < cfg.min_transfer:
            raise CreditTransferError("amount_below_min", f"Minimum transfer is {cfg.min_transfer}", 422)

        if amount > cfg.max_transfer:
            raise CreditTransferError("amount_above_max", f"Maximum transfer is {cfg.max_transfer}", 422)

        if spendable < amount:
            raise CreditTransferError("insufficient_credits", "Insufficient spendable credits", 402)

        if (daily_sent + amount) > cfg.daily_cap:
            raise CreditTransferError("daily_cap_exceeded", "Daily transfer cap exceeded", 429)

        if per_min_count >= cfg.per_minute_limit:
            raise CreditTransferError("rate_limit_exceeded", "Transfer rate limit exceeded", 429)

        sender_email = self._normalize_email(sender.email)
        if sender_email == recipient_email:
            raise CreditTransferError("self_transfer", "You cannot transfer credits to yourself", 422)

        created_at = getattr(sender, "created_at", None)
        if cfg.account_age_minutes_min > 0 and created_at:
            min_age = timedelta(minutes=cfg.account_age_minutes_min)
            if datetime.utcnow() - created_at < min_age:
                raise CreditTransferError("account_too_new", "Account age requirement not met", 403)

    def get_balance_view(self, session: Session, user: User, cfg: CreditTransferConfig) -> BalanceView:
        now = datetime.utcnow()
        day_start = datetime(now.year, now.month, now.day)
        spendable = Decimal(str(compute_user_balance(session, user.id)))
        pending_out = Decimal(
            str(
                session.exec(
                    select(func.coalesce(func.sum(CreditTransfer.amount), 0))
                    .where(CreditTransfer.sender_user_id == user.id)
                    .where(CreditTransfer.status == "PENDING")
                ).one()
                or 0
            )
        )
        sent_today = self._daily_sent(session, user.id, day_start)
        daily_remaining = max(Decimal("0"), cfg.daily_cap - sent_today)

        reason = None
        can_transfer = True
        if not cfg.enabled:
            can_transfer = False
            reason = "Credit transfer is disabled"
        elif spendable < cfg.min_transfer:
            can_transfer = False
            reason = "No credits available"
        elif daily_remaining < cfg.min_transfer:
            can_transfer = False
            reason = "Daily transfer limit reached"

        return BalanceView(
            spendable_balance=spendable,
            pending_outgoing_total=pending_out,
            can_transfer=can_transfer,
            min_transfer=cfg.min_transfer,
            max_transfer=cfg.max_transfer,
            daily_remaining=daily_remaining,
            reason_if_disabled=reason,
            credit_transfer_enabled=cfg.enabled,
        )

    def create_transfer(
        self,
        session: Session,
        *,
        sender: User,
        recipient_email_raw: str,
        amount: Decimal,
        idempotency_key: str,
        cfg: CreditTransferConfig,
        sender_ip: Optional[str] = None,
    ) -> CreditTransfer:
        if not idempotency_key or not idempotency_key.strip():
            raise CreditTransferError("missing_idempotency_key", "idempotency_key is required", 422)

        recipient_email = self._normalize_email(recipient_email_raw)
        if not recipient_email or "@" not in recipient_email:
            raise CreditTransferError("invalid_email", "Valid recipient_email is required", 422)

        amount = Decimal(str(amount))

        existing = session.exec(
            select(CreditTransfer)
            .where(CreditTransfer.sender_user_id == sender.id)
            .where(CreditTransfer.idempotency_key == idempotency_key.strip())
        ).first()
        if existing:
            return existing

        sender_locked = session.exec(select(User).where(User.id == sender.id).with_for_update()).first()
        if not sender_locked:
            raise CreditTransferError("sender_not_found", "Sender account not found", 404)

        spendable_before = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, sender.id)))
        now = datetime.utcnow()
        day_start = datetime(now.year, now.month, now.day)
        per_min_since = now - timedelta(minutes=1)

        sender_ip_hash = self._hash_ip(sender_ip)
        self._validate_limits(
            sender=sender_locked,
            recipient_email=recipient_email,
            amount=amount,
            spendable=spendable_before,
            cfg=cfg,
            daily_sent=self._daily_sent(session, sender.id, day_start),
            per_min_count=self._per_minute_count(session, sender.id, per_min_since),
        )
        if sender_ip_hash:
            ip_count = self._per_minute_ip_count(session, sender_ip_hash, per_min_since)
            if ip_count >= max(1, cfg.per_minute_limit * 3):
                raise CreditTransferError("ip_rate_limit_exceeded", "Transfer IP rate limit exceeded", 429)

        transfer = CreditTransfer(
            sender_user_id=sender.id,
            recipient_email=recipient_email,
            recipient_user_id=None,
            amount=amount,
            status="PENDING",
            idempotency_key=idempotency_key.strip(),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=max(1, cfg.pending_expiry_days)),
            sender_ip_hash=sender_ip_hash,
        )
        session.add(transfer)
        session.flush()

        billing_ledger_service_v2._allocate_credits_fifo(session, sender.id, amount, attempt_id=transfer.id)

        escrow_lot = CreditLot(
            user_id=sender.id,
            subscription_id=None,
            credits_total=amount,
            credits_remaining=amount,
            lot_type="TRANSFER_ESCROW",
            status="HELD",
            source="CREDIT_TRANSFER",
            external_ref=transfer.id,
            purchased_at=now,
            expires_at=transfer.expires_at,
            source_attempt_id=transfer.id,
            reason_code="TRANSFER_PENDING",
        )
        session.add(escrow_lot)
        session.flush()

        spendable_after_sender = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, sender.id)))
        sender_ledger = BillingLedger(
            user_id=sender.id,
            action_type="TRANSFER_OUT",
            request_id=transfer.id,
            idempotency_key=f"transfer:out:{transfer.id}",
            status="SETTLED",
            credits_charged=amount,
            estimated_credits=amount,
            actual_credits=amount,
            delta_credits=Decimal("0") - amount,
            credits_before=spendable_before,
            credits_after=spendable_after_sender,
            tier="STANDARD",
            ok=True,
            finalized_at=now,
        )
        session.add(sender_ledger)
        session.flush()

        transfer.escrow_lot_id = escrow_lot.id
        transfer.sender_ledger_id = sender_ledger.id

        recipient = self._recipient_user(session, recipient_email)
        if recipient and recipient.id != sender.id:
            recipient_locked = session.exec(select(User).where(User.id == recipient.id).with_for_update()).first()
            if recipient_locked:
                recipient_before = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, recipient.id)))
                escrow_lot.user_id = recipient.id
                escrow_lot.status = "ACTIVE"
                escrow_lot.lot_type = "TRANSFER_IN"
                escrow_lot.source = "CREDIT_TRANSFER"
                escrow_lot.reason_code = "TRANSFER_CLAIMED"
                escrow_lot.expires_at = None
                session.add(escrow_lot)

                recipient_after = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, recipient.id)))
                recipient_ledger = BillingLedger(
                    user_id=recipient.id,
                    action_type="TRANSFER_IN",
                    request_id=transfer.id,
                    idempotency_key=f"transfer:in:{transfer.id}",
                    status="SETTLED",
                    credits_charged=Decimal("0"),
                    estimated_credits=Decimal("0"),
                    actual_credits=Decimal("0"),
                    delta_credits=amount,
                    credits_before=recipient_before,
                    credits_after=recipient_after,
                    tier="STANDARD",
                    ok=True,
                    finalized_at=now,
                )
                session.add(recipient_ledger)
                session.flush()

                transfer.status = "COMPLETED"
                transfer.recipient_user_id = recipient.id
                transfer.recipient_ledger_id = recipient_ledger.id
                transfer.claimed_at = now

        transfer.updated_at = datetime.utcnow()
        session.add(transfer)

        sender_locked.credits_balance = float(compute_user_balance(session, sender.id))
        session.add(sender_locked)
        if transfer.recipient_user_id:
            recipient_locked = session.exec(select(User).where(User.id == transfer.recipient_user_id).with_for_update()).first()
            if recipient_locked:
                recipient_locked.credits_balance = float(compute_user_balance(session, recipient_locked.id))
                session.add(recipient_locked)

        session.flush()
        return transfer

    def claim_pending_for_user(self, session: Session, user: User) -> List[CreditTransfer]:
        email = self._normalize_email(user.email)
        now = datetime.utcnow()
        pending = session.exec(
            select(CreditTransfer)
            .where(CreditTransfer.recipient_email == email)
            .where(CreditTransfer.status == "PENDING")
            .where(CreditTransfer.expires_at > now)
            .with_for_update()
        ).all()

        claimed: List[CreditTransfer] = []
        recipient_locked = session.exec(select(User).where(User.id == user.id).with_for_update()).first()
        if not recipient_locked:
            return claimed

        for transfer in pending:
            if not transfer.escrow_lot_id:
                transfer.status = "CANCELED"
                transfer.failure_reason = "missing_escrow_lot"
                transfer.updated_at = now
                session.add(transfer)
                continue

            lot = session.get(CreditLot, transfer.escrow_lot_id)
            if not lot or lot.status != "HELD":
                transfer.status = "CANCELED"
                transfer.failure_reason = "invalid_escrow_lot"
                transfer.updated_at = now
                session.add(transfer)
                continue

            before = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, user.id)))
            lot.user_id = user.id
            lot.status = "ACTIVE"
            lot.lot_type = "TRANSFER_IN"
            lot.source = "CREDIT_TRANSFER"
            lot.reason_code = "TRANSFER_CLAIMED"
            lot.expires_at = None
            session.add(lot)
            after = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, user.id)))

            recipient_ledger = BillingLedger(
                user_id=user.id,
                action_type="TRANSFER_IN",
                request_id=transfer.id,
                idempotency_key=f"transfer:in:{transfer.id}",
                status="SETTLED",
                credits_charged=Decimal("0"),
                estimated_credits=Decimal("0"),
                actual_credits=Decimal("0"),
                delta_credits=Decimal(str(transfer.amount)),
                credits_before=before,
                credits_after=after,
                tier="STANDARD",
                ok=True,
                finalized_at=now,
            )
            session.add(recipient_ledger)
            session.flush()

            transfer.status = "COMPLETED"
            transfer.recipient_user_id = user.id
            transfer.claimed_at = now
            transfer.updated_at = now
            transfer.recipient_ledger_id = recipient_ledger.id
            session.add(transfer)
            claimed.append(transfer)

        recipient_locked.credits_balance = float(compute_user_balance(session, user.id))
        session.add(recipient_locked)
        session.flush()
        return claimed

    def expire_and_refund_pending(self, session: Session, *, now: Optional[datetime] = None) -> List[CreditTransfer]:
        now = now or datetime.utcnow()
        expired = session.exec(
            select(CreditTransfer)
            .where(CreditTransfer.status == "PENDING")
            .where(CreditTransfer.expires_at <= now)
            .with_for_update()
        ).all()
        processed: List[CreditTransfer] = []
        for transfer in expired:
            sender = session.exec(select(User).where(User.id == transfer.sender_user_id).with_for_update()).first()
            lot = session.get(CreditLot, transfer.escrow_lot_id) if transfer.escrow_lot_id else None
            if not sender or not lot:
                transfer.status = "CANCELED"
                transfer.failure_reason = "missing_sender_or_escrow"
                transfer.updated_at = now
                session.add(transfer)
                processed.append(transfer)
                continue

            before = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, sender.id)))
            lot.status = "ACTIVE"
            lot.lot_type = "REFUND"
            lot.source = "CREDIT_TRANSFER"
            lot.reason_code = "TRANSFER_EXPIRED_REFUND"
            lot.expires_at = None
            session.add(lot)
            after = Decimal(str(billing_ledger_service_v2._compute_available_balance_locked(session, sender.id)))

            ledger = BillingLedger(
                user_id=sender.id,
                action_type="TRANSFER_REFUND",
                request_id=transfer.id,
                idempotency_key=f"transfer:refund:{transfer.id}",
                status="SETTLED",
                credits_charged=Decimal("0"),
                estimated_credits=Decimal("0"),
                actual_credits=Decimal("0"),
                delta_credits=Decimal(str(transfer.amount)),
                credits_before=before,
                credits_after=after,
                tier="STANDARD",
                ok=True,
                finalized_at=now,
            )
            session.add(ledger)
            session.flush()

            transfer.status = "REFUNDED"
            transfer.failure_reason = "expired_refund"
            transfer.updated_at = now
            transfer.refund_ledger_id = ledger.id
            session.add(transfer)
            sender.credits_balance = float(compute_user_balance(session, sender.id))
            session.add(sender)
            processed.append(transfer)

        session.flush()
        return processed


credit_transfer_service = CreditTransferService()

