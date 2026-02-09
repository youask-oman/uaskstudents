import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from sqlmodel import Session, select

from app.database import engine
from app.models import (
    Payment,
    PromptBinding,
    PromptTemplateEntry,
    ProviderModelPricing,
    School,
    SystemConfig,
    User,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"


def _run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def _counts() -> Dict[str, int]:
    with Session(engine) as session:
        return {
            "school": len(session.exec(select(School)).all()),
            "systemconfig": len(session.exec(select(SystemConfig)).all()),
            "prompt_templates_active": len(
                session.exec(select(PromptTemplateEntry).where(PromptTemplateEntry.is_active == True)).all()
            ),
            "prompt_bindings_active": len(
                session.exec(select(PromptBinding).where(PromptBinding.is_active == True)).all()
            ),
            "providermodelpricing_active": len(
                session.exec(select(ProviderModelPricing).where(ProviderModelPricing.status == "ACTIVE")).all()
            ),
            "internal_users": len(
                session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all()
            ),
            "payment_rows": len(session.exec(select(Payment)).all()),
        }


def main() -> None:
    os.environ["APP_ENV"] = "DEV"
    os.environ.setdefault("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")

    _run([sys.executable, str(SCRIPTS_DIR / "dev_reset_db.py"), "--mode", "NUKE", "--confirm", "RESET_DEV_DB"])
    _run(["alembic", "upgrade", "head"])
    _run([sys.executable, str(SCRIPTS_DIR / "seed_production.py"), "--env", "DEV"])
    _run(["pytest", "tests/smoke/", "-q"])

    summary = _counts()
    print("DEV seed+smoke summary")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
