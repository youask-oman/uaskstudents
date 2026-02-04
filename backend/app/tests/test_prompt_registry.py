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


def test_schema_update_accepts_openai_wrapper_and_normalizes(tmp_path):
    session = _make_session(tmp_path)
    wrapped = {
        "type": "json_schema",
        "json_schema": {
            "name": "wrapped_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    }

    assert prompt_registry_service.validate_schema(wrapped) is None
    entry = prompt_registry_service.update_schema(
        session=session,
        schema_id="wrapped_schema_v1",
        content=wrapped,
        updated_by="tester",
    )
    assert entry.content.get("type") == "object"
    assert "json_schema" not in entry.content


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

    source_dir = repo_root / "static_design" / "sug_prompts_openai"
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
        session, prompt_registry_service.OCR_EXTRACT_OPENAI_SYSTEM_PROMPT_ID
    )
    schema = prompt_registry_service.get_active_schema(
        session, prompt_registry_service.OCR_EXTRACT_OPENAI_SCHEMA_ID
    )

    assert system_prompt is not None
    assert schema is not None


def test_ensure_standard_solve_binding_sets_extreme_default_and_deactivates_legacy(tmp_path):
    session = _make_session(tmp_path)

    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="GLOBAL_SYSTEM",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_moderate_v1",
        content="STD_V1",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_standard_solve_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="solve_standard_moderate_v1",
        output_schema_id="youask_math_solver_standard_solve_v1",
        updated_by="tester",
    )

    prompt_registry_service.ensure_standard_solve_binding(session, updated_by="tester")

    binding = prompt_registry_service.get_active_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
    )
    assert binding is not None
    assert binding.developer_prompt_id == "solve_standard_extreme_detailed_v1"
    assert binding.output_schema_id == "youask_math_solver_standard_solve_extreme_v1"
    assert prompt_registry_service.get_active_prompt(session, "solve_standard_extreme_detailed_v1") is not None
    assert prompt_registry_service.get_active_schema(session, "youask_math_solver_standard_solve_extreme_v1") is not None
    assert prompt_registry_service.get_active_prompt(session, "solve_standard_moderate_v1") is None
    assert prompt_registry_service.get_active_schema(session, "youask_math_solver_standard_solve_v1") is None


def test_ensure_freeform_solve_prompts_by_tier_uses_updated_assets(tmp_path):
    session = _make_session(tmp_path)
    created = prompt_registry_service.ensure_freeform_solve_prompts_by_tier(session, updated_by="tester")

    repo_root = Path(__file__).resolve().parents[3]
    expected_assets = {
        prompt_registry_service.FREEFORM_SOLVE_FREE_PROMPT_ID: repo_root
        / "static_design"
        / "sug_prompts_openai"
        / "free_form_math_free_fast_v1.txt",
        prompt_registry_service.FREEFORM_SOLVE_PROMPT_ID: repo_root
        / "static_design"
        / "sug_prompts_openai"
        / "free_form_math_standard_detailed.txt",
        prompt_registry_service.FREEFORM_SOLVE_RESEARCH_PROMPT_ID: repo_root
        / "static_design"
        / "sug_prompts_openai"
        / "free_form_math_research_rigorous_v1.txt",
    }

    assert set(created.keys()) == set(expected_assets.keys())
    for prompt_id, path in expected_assets.items():
        row = prompt_registry_service.get_active_prompt(session, prompt_id)
        assert row is not None
        assert row.content == path.read_text(encoding="utf-8").strip()


def test_delete_prompt_rebinds_active_binding_when_replacement_exists(tmp_path):
    session = _make_session(tmp_path)

    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="GLOBAL_PRIMARY",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_backup_v1",
        content="GLOBAL_BACKUP",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_delete_me_v1",
        content="DELETE_ME",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_backup_v1",
        content="BACKUP",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_standard_solve_extreme_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="solve_standard_delete_me_v1",
        output_schema_id="youask_math_solver_standard_solve_extreme_v1",
        updated_by="tester",
    )

    result = prompt_registry_service.delete_prompt(
        session=session,
        prompt_id="solve_standard_delete_me_v1",
        updated_by="tester",
    )

    assert result["deleted_versions"] == 1
    assert result["rebound_bindings"] == 1
    assert result["deactivated_bindings"] == 0
    assert prompt_registry_service.get_active_prompt(session, "solve_standard_delete_me_v1") is None

    binding = prompt_registry_service.get_active_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE)
    assert binding is not None
    assert binding.developer_prompt_id == "solve_standard_backup_v1"


def test_delete_prompt_deactivates_binding_when_no_replacement_exists(tmp_path):
    session = _make_session(tmp_path)

    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="GLOBAL_PRIMARY",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_only_v1",
        content="ONLY_PROMPT",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="youask_math_solver_standard_solve_extreme_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="solve_standard_only_v1",
        output_schema_id="youask_math_solver_standard_solve_extreme_v1",
        updated_by="tester",
    )

    result = prompt_registry_service.delete_prompt(
        session=session,
        prompt_id="solve_standard_only_v1",
        updated_by="tester",
    )

    assert result["deleted_versions"] == 1
    assert result["rebound_bindings"] == 0
    assert result["deactivated_bindings"] == 1
    assert prompt_registry_service.get_active_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE) is None


def test_delete_schema_rebinds_active_binding_when_replacement_exists(tmp_path):
    session = _make_session(tmp_path)

    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="GLOBAL",
        tier=None,
        mode=PromptModeEnum.VERIFY,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="verify_v1",
        content="VERIFY_PROMPT",
        tier=None,
        mode=PromptModeEnum.VERIFY,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="verify_schema_delete_me_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="verify_schema_backup_v1",
        content={"type": "object", "title": "backup"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.FREE,
        mode=PromptModeEnum.VERIFY,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="verify_v1",
        output_schema_id="verify_schema_backup_v1",
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.VERIFY,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="verify_v1",
        output_schema_id="verify_schema_delete_me_v1",
        updated_by="tester",
    )

    result = prompt_registry_service.delete_schema(
        session=session,
        schema_id="verify_schema_delete_me_v1",
        updated_by="tester",
    )

    assert result["deleted_versions"] == 1
    assert result["rebound_bindings"] == 1
    assert result["deactivated_bindings"] == 0
    assert prompt_registry_service.get_active_schema(session, "verify_schema_delete_me_v1") is None
    binding = prompt_registry_service.get_active_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.VERIFY)
    assert binding is not None
    assert binding.output_schema_id == "verify_schema_backup_v1"


def test_delete_schema_deactivates_binding_when_no_replacement_exists(tmp_path):
    session = _make_session(tmp_path)

    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="GLOBAL",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_only_v1",
        content="ONLY",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id="schema_only_v1",
        content={"type": "object"},
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="solve_standard_only_v1",
        output_schema_id="schema_only_v1",
        updated_by="tester",
    )

    result = prompt_registry_service.delete_schema(
        session=session,
        schema_id="schema_only_v1",
        updated_by="tester",
    )

    assert result["deleted_versions"] == 1
    assert result["rebound_bindings"] == 0
    assert result["deactivated_bindings"] == 1
    assert prompt_registry_service.get_active_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE) is None
