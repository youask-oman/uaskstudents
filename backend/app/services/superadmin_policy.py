import os

from sqlmodel import Session

from app.models import User


def get_forced_superadmin_emails() -> set[str]:
    primary = os.environ.get("SEED_PRIMARY_SUPERADMIN_EMAIL", "admin@uask.ai")
    secondary = os.environ.get("SEED_SECOND_SUPERADMIN_EMAIL", "loai@uask.ai")
    extra = os.environ.get("FORCE_SUPERADMIN_EMAILS", "")
    values = [primary, secondary, *extra.split(",")]
    return {v.strip().lower() for v in values if v and v.strip()}


def is_forced_superadmin_email(email: str | None) -> bool:
    return bool(email and email.strip().lower() in get_forced_superadmin_emails())


def enforce_superadmin_role(session: Session, user: User) -> bool:
    if not user or not is_forced_superadmin_email(getattr(user, "email", None)):
        return False
    if str(getattr(user, "role", "")).strip().lower() == "superadmin":
        return False
    user.role = "superadmin"
    session.add(user)
    session.commit()
    session.refresh(user)
    return True


def is_protected_superadmin_user(user: User | None) -> bool:
    if not user:
        return False
    return is_forced_superadmin_email(getattr(user, "email", None))
