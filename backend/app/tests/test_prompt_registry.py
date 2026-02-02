import sys
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import PromptTierEnum, PromptModeEnum, PromptRoleEnum, PromptTemplateEntry, JsonSchemaEntry
from app.services.prompt_registry_service import prompt_registry_service


def _make_session(tmp_path):
    db_path = tmp_path / "registry.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_prompt_versioning(tmp_path):
    session = _make_session(tmp_path)
    entry1 = prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_free_minimal_v1",
        content="v1",
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    entry2 = prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_free_minimal_v1",
        content="v2",
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    assert entry2.version == entry1.version + 1
    active = prompt_registry_service.get_active_prompt(session, "solve_free_minimal_v1")
    assert active.version == entry2.version


def test_schema_versioning(tmp_path):
    session = _make_session(tmp_path)
    entry1 = prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_response_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    entry2 = prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_response_v1",
        content={"type": "object", "title": "v2"},
        updated_by="tester",
    )
    assert entry2.version == entry1.version + 1
    active = prompt_registry_service.get_active_schema(session, "youask_math_solver_response_v1")
    assert active.version == entry2.version


def test_import_script_loads_assets(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "import_prompts_and_schemas.py"
    sys.path.append(str(repo_root))

    import importlib.util
    spec = importlib.util.spec_from_file_location("import_prompts_and_schemas", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_import = module.run_import

    db_path = tmp_path / "import.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    source_dir = repo_root / "static_design" / "sug_prompts_qwen"
    run_import(source_dir)

    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        prompt = prompt_registry_service.get_active_prompt(session, "solve_free_minimal_v1")
        schema = prompt_registry_service.get_active_schema(session, "youask_math_solver_response_v1")
        assert prompt is not None
        assert schema is not None


def test_ensure_ocr_extract_prompts(tmp_path):
    session = _make_session(tmp_path)
    prompt_registry_service.ensure_ocr_extract_prompts(session, updated_by="tester")

    system_prompt = prompt_registry_service.get_active_prompt(
        session, prompt_registry_service.OCR_EXTRACT_QWEN_SYSTEM_PROMPT_ID
    )
    user_prompt = prompt_registry_service.get_active_prompt(
        session, prompt_registry_service.OCR_EXTRACT_QWEN_USER_PROMPT_ID
    )

    assert system_prompt is not None
    assert user_prompt is not None
    assert "Extract ALL math questions from the provided image or PDF page image(s)." in user_prompt.content
