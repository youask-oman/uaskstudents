import os
import json
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models import User
from scripts.seed_production import run_seed


def test_internal_users_exist():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    with Session(engine) as session:
        users = session.exec(
            select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai")).order_by(User.email.asc())
        ).all()
        seed_file = Path(__file__).resolve().parents[2] / "seed_data" / "internal_users.json"
        expected = len(json.loads(seed_file.read_text(encoding="utf-8")))
        assert len(users) == expected
        allowed_internal_roles = {
            "admin",
            "employee",
            "superadmin",
            "supervisor",
            "support",
            "finance",
            "devops",
        }
        assert all((u.role or "").lower() in allowed_internal_roles for u in users)
