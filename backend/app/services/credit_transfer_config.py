from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session


@dataclass
class CreditTransferConfig:
    enabled: bool
    notifications_enabled: bool
    min_transfer: Decimal
    max_transfer: Decimal
    daily_cap: Decimal
    pending_expiry_days: int
    per_minute_limit: int
    thank_per_minute_limit: int
    account_age_minutes_min: int


def _cfg_value(session: Session, key: str, default: str) -> str:
    _ = session
    val = os.getenv(key)
    if val is not None and str(val).strip() != "":
        return str(val).strip()
    return default


def _to_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_credit_transfer_config(session: Session) -> CreditTransferConfig:
    enabled_default = os.getenv("CREDIT_TRANSFER_ENABLED", "false")
    notif_default = os.getenv("NOTIFICATIONS_ENABLED", "true")

    return CreditTransferConfig(
        enabled=_to_bool(_cfg_value(session, "CREDIT_TRANSFER_ENABLED", enabled_default)),
        notifications_enabled=_to_bool(_cfg_value(session, "NOTIFICATIONS_ENABLED", notif_default)),
        min_transfer=Decimal(_cfg_value(session, "CREDIT_TRANSFER_MIN", os.getenv("CREDIT_TRANSFER_MIN", "1"))),
        max_transfer=Decimal(_cfg_value(session, "CREDIT_TRANSFER_MAX", os.getenv("CREDIT_TRANSFER_MAX", "1000"))),
        daily_cap=Decimal(_cfg_value(session, "CREDIT_TRANSFER_DAILY_CAP", os.getenv("CREDIT_TRANSFER_DAILY_CAP", "5000"))),
        pending_expiry_days=int(_cfg_value(session, "CREDIT_TRANSFER_PENDING_EXPIRY_DAYS", os.getenv("CREDIT_TRANSFER_PENDING_EXPIRY_DAYS", "30"))),
        per_minute_limit=int(_cfg_value(session, "CREDIT_TRANSFER_PER_MIN_LIMIT", os.getenv("CREDIT_TRANSFER_PER_MIN_LIMIT", "10"))),
        thank_per_minute_limit=int(_cfg_value(session, "NOTIFICATIONS_THANK_PER_MIN_LIMIT", os.getenv("NOTIFICATIONS_THANK_PER_MIN_LIMIT", "5"))),
        account_age_minutes_min=int(_cfg_value(session, "CREDIT_TRANSFER_ACCOUNT_AGE_MINUTES", os.getenv("CREDIT_TRANSFER_ACCOUNT_AGE_MINUTES", "0"))),
    )

