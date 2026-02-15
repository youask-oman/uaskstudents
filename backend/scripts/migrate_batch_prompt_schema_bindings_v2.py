from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Tuple

from dotenv import load_dotenv
from sqlmodel import Session, create_engine, select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
PROMPTS_DIR = BACKEND_ROOT / "app" / "prompts" / "openai_prompts"
SCHEMAS_DIR = BACKEND_ROOT / "app" / "schemas" / "openai_schemas"

from app.models import (
    JsonSchemaEntry,
    PromptBinding,
    PromptModeEnum,
    PromptRoleEnum,
    PromptTemplateEntry,
    PromptTierEnum,
)

SYSTEM_PROMPT_ID = "prompt__global_system_prompt_batch_v1.txt"
DEV_PROMPTS = {
    PromptTierEnum.SHORT: "prompt__solve_dev_final_v2.txt",
    PromptTierEnum.FREE: "prompt__solve_dev_free_v2.txt",
    PromptTierEnum.STANDARD: "prompt__solve_dev_standard_v2.txt",
    PromptTierEnum.RESEARCH: "prompt__solve_dev_research_v2.txt",
}
TIER_SCHEMAS = {
    PromptTierEnum.SHORT: "schema__solve_batch_final_v2.schema.json",
    PromptTierEnum.FREE: "schema__solve_batch_free_v2.schema.json",
    PromptTierEnum.STANDARD: "schema__solve_batch_standard_v2.schema.json",
    PromptTierEnum.RESEARCH: "schema__solve_batch_research_v2.schema.json",
}
TIER_SCHEMA_SOURCES = {
    PromptTierEnum.SHORT: "schema__solve_batch_final_v2.schema_openai_strict.json",
    PromptTierEnum.FREE: "schema__solve_batch_free_v2.schema_openai_strict.json",
    PromptTierEnum.STANDARD: "schema__solve_batch_standard_v2.schema_openai_strict.json",
    PromptTierEnum.RESEARCH: "schema__solve_batch_research_v2.schema_openai_strict.json",
}


def _load_text(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Missing required prompt file: {path}")
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Dict:
    if not path.exists():
        raise RuntimeError(f"Missing required schema file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_prompt(
    session: Session,
    *,
    prompt_id: str,
    content: str,
    role: PromptRoleEnum,
    tier: PromptTierEnum | None,
) -> None:
    row = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .order_by(PromptTemplateEntry.version.desc())
    ).first()
    if row:
        row.content = content
        row.role = role
        row.mode = PromptModeEnum.SOLVE
        row.tier = tier
        row.updated_by = "batch_migration_v2"
        session.add(row)
        return

    session.add(
        PromptTemplateEntry(
            prompt_id=prompt_id,
            mode=PromptModeEnum.SOLVE,
            role=role,
            tier=tier,
            content=content,
            version=1,
            is_active=True,
            updated_by="batch_migration_v2",
        )
    )


def _upsert_schema(session: Session, *, schema_id: str, content: Dict) -> None:
    row = session.exec(
        select(JsonSchemaEntry)
        .where(JsonSchemaEntry.schema_id == schema_id)
        .where(JsonSchemaEntry.is_active == True)
        .order_by(JsonSchemaEntry.version.desc())
    ).first()
    if row:
        row.content = content
        row.updated_by = "batch_migration_v2"
        session.add(row)
        return

    session.add(
        JsonSchemaEntry(
            schema_id=schema_id,
            content=content,
            version=1,
            is_active=True,
            updated_by="batch_migration_v2",
        )
    )


def _activate_binding(
    session: Session,
    *,
    tier: PromptTierEnum,
    developer_prompt_id: str,
    schema_id: str,
) -> None:
    rows = session.exec(
        select(PromptBinding)
        .where(PromptBinding.tier == tier)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
    ).all()
    target = None
    for row in rows:
        if (
            row.global_system_prompt_id == SYSTEM_PROMPT_ID
            and row.developer_prompt_id == developer_prompt_id
            and row.output_schema_id == schema_id
        ):
            target = row
        row.is_active = False
        row.updated_by = "batch_migration_v2"
        session.add(row)

    if target is not None:
        target.is_active = True
        target.updated_by = "batch_migration_v2"
        session.add(target)
        return

    session.add(
        PromptBinding(
            tier=tier,
            mode=PromptModeEnum.SOLVE,
            global_system_prompt_id=SYSTEM_PROMPT_ID,
            developer_prompt_id=developer_prompt_id,
            output_schema_id=schema_id,
            is_active=True,
            updated_by="batch_migration_v2",
            features={},
            multipliers={},
        )
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(database_url)

    system_content = _load_text(PROMPTS_DIR / SYSTEM_PROMPT_ID)
    dev_contents: Dict[PromptTierEnum, str] = {
        tier: _load_text(PROMPTS_DIR / pid) for tier, pid in DEV_PROMPTS.items()
    }
    schema_contents: Dict[PromptTierEnum, Dict] = {}
    for tier, schema_id in TIER_SCHEMAS.items():
        strict_source = SCHEMAS_DIR / TIER_SCHEMA_SOURCES[tier]
        default_source = SCHEMAS_DIR / schema_id
        source_path = strict_source if strict_source.exists() else default_source
        schema_contents[tier] = _load_json(source_path)

    with Session(engine) as session:
        _upsert_prompt(
            session,
            prompt_id=SYSTEM_PROMPT_ID,
            content=system_content,
            role=PromptRoleEnum.SYSTEM,
            tier=None,
        )
        for tier, prompt_id in DEV_PROMPTS.items():
            _upsert_prompt(
                session,
                prompt_id=prompt_id,
                content=dev_contents[tier],
                role=PromptRoleEnum.DEVELOPER,
                tier=tier,
            )
        for tier, schema_id in TIER_SCHEMAS.items():
            _upsert_schema(session, schema_id=schema_id, content=schema_contents[tier])
        for tier, prompt_id in DEV_PROMPTS.items():
            _activate_binding(
                session,
                tier=tier,
                developer_prompt_id=prompt_id,
                schema_id=TIER_SCHEMAS[tier],
            )
        session.commit()

    print(
        json.dumps(
            {
                "ok": True,
                "system_prompt_id": SYSTEM_PROMPT_ID,
                "developer_prompts": list(DEV_PROMPTS.values()),
                "schemas": list(TIER_SCHEMAS.values()),
                "bindings_tiers": [tier.value for tier in DEV_PROMPTS.keys()],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
