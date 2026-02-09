import json
import os
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models import JsonSchemaEntry, PromptBinding, PromptTemplateEntry
from app.models.credit_program_models import CreditProgramDefinition
from app.models import Plan, ProviderModelPricing, SystemConfig, User
from scripts.export_prompt_and_schema_seeds import export_all
from scripts.seed_production import run_seed


ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "seed_data"


def _db_counts() -> dict:
    with Session(engine) as session:
        return {
            "systemconfig.json": len(session.exec(select(SystemConfig)).all()),
            "json_schemas.json": len(session.exec(select(JsonSchemaEntry)).all()),
            "prompt_templates.json": len(session.exec(select(PromptTemplateEntry)).all()),
            "prompt_bindings.json": len(session.exec(select(PromptBinding)).all()),
            "providermodelpricing.json": len(session.exec(select(ProviderModelPricing)).all()),
            "credit_programs_or_plans.json": (
                len(session.exec(select(CreditProgramDefinition)).all()) + len(session.exec(select(Plan)).all())
            ),
            "internal_users.json": len(
                session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all()
            ),
        }


def test_prompt_schema_seed_fidelity():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"

    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    export_all(SEED_DIR)
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)

    manifest = json.loads((SEED_DIR / "seed_manifest.json").read_text(encoding="utf-8"))
    files_meta = manifest["files"]
    counts = _db_counts()
    for name, expected_count in ((k, v["row_count"]) for k, v in files_meta.items() if k in counts):
        assert counts[name] == expected_count, f"{name}: db={counts[name]} manifest={expected_count}"

    with Session(engine) as session:
        prompt_ids = set(session.exec(select(PromptTemplateEntry.prompt_id).distinct()).all())
        schema_ids = set(session.exec(select(JsonSchemaEntry.schema_id).distinct()).all())
        bindings = session.exec(select(PromptBinding)).all()
        dangling = []
        for b in bindings:
            if b.global_system_prompt_id not in prompt_ids:
                dangling.append(("global_system_prompt_id", b.global_system_prompt_id, b.id))
            if b.developer_prompt_id not in prompt_ids:
                dangling.append(("developer_prompt_id", b.developer_prompt_id, b.id))
            if b.output_schema_id not in schema_ids:
                dangling.append(("output_schema_id", b.output_schema_id, b.id))
        assert not dangling, f"Dangling prompt/schema references: {dangling}"
