import os

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
        assert len(users) == 10
        assert all(u.role in {"admin", "employee", "superadmin"} for u in users)
