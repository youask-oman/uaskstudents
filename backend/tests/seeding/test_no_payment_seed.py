import os

from sqlmodel import Session, select

from app.database import engine
from app.models import Payment
from scripts.seed_production import run_seed


def test_no_payment_seed():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    with Session(engine) as session:
        assert len(session.exec(select(Payment)).all()) == 0
