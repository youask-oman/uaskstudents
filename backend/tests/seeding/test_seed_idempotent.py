import os

from sqlmodel import Session, select

from app.database import engine
from app.models import PromptBinding, PromptTemplateEntry, ProviderModelPricing, School, SystemConfig
from scripts.seed_production import run_seed


def _counts():
    with Session(engine) as session:
        return {
            "school": len(session.exec(select(School)).all()),
            "systemconfig": len(session.exec(select(SystemConfig)).all()),
            "prompt_templates": len(
                session.exec(select(PromptTemplateEntry).where(PromptTemplateEntry.is_active == True)).all()
            ),
            "prompt_bindings": len(session.exec(select(PromptBinding).where(PromptBinding.is_active == True)).all()),
            "pricing": len(session.exec(select(ProviderModelPricing).where(ProviderModelPricing.status == "ACTIVE")).all()),
        }


def test_seed_idempotent():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    first = _counts()
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    second = _counts()
    assert first == second
