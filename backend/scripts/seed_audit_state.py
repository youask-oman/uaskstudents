from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import sys

from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import get_password_hash
from app.database import create_db_and_tables, engine
from app.models import User


AUDIT_EMAIL = "audit@uask.ai"
AUDIT_PASSWORD = "admin1234"


def main() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == AUDIT_EMAIL)).first()
        if user is None:
            user = User(
                email=AUDIT_EMAIL,
                full_name="Audit User",
                password_hash=get_password_hash(AUDIT_PASSWORD),
                role="admin",
                is_verified=True,
                subscription_tier="standard",
                credits_balance=Decimal("1000"),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        else:
            user.subscription_tier = "standard"
            user.credits_balance = Decimal("1000")
            user.password_hash = get_password_hash(AUDIT_PASSWORD)
            user.is_verified = True
            session.add(user)
            session.commit()

        report = {
            "ok": True,
            "email": AUDIT_EMAIL,
            "password": AUDIT_PASSWORD,
            "user_id": user.id,
            "subscription_tier": user.subscription_tier,
            "credits_balance": str(user.credits_balance),
        }
        out = Path("reports/evidence/seed_audit_state.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
