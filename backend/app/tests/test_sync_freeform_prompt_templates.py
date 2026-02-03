import importlib.util
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import PromptModeEnum, PromptRoleEnum, PromptTemplateEntry


def _load_sync_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "backend" / "scripts" / "sync_freeform_prompt_templates.py"
    spec = importlib.util.spec_from_file_location("sync_freeform_prompt_templates", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sync_freeform_prompt_templates_is_idempotent(tmp_path):
    module = _load_sync_module()
    db_path = tmp_path / "freeform_prompts.db"
    db_url = f"sqlite:///{db_path}"

    report_first = module.sync_freeform_prompt_templates(
        database_url=db_url,
        updated_by="test_sync_first",
    )
    assert report_first["changed_count"] == 3
    assert report_first["unchanged_count"] == 0

    report_second = module.sync_freeform_prompt_templates(
        database_url=db_url,
        updated_by="test_sync_second",
    )
    assert report_second["changed_count"] == 0
    assert report_second["unchanged_count"] == 3

    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    expected_assets = {target.prompt_id: target.asset_path.read_text(encoding="utf-8") for target in module.DEFAULT_TARGETS}

    with Session(engine) as session:
        for prompt_id, expected_content in expected_assets.items():
            active_rows = session.exec(
                select(PromptTemplateEntry)
                .where(PromptTemplateEntry.prompt_id == prompt_id)
                .where(PromptTemplateEntry.mode == PromptModeEnum.SOLVE)
                .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
                .where(PromptTemplateEntry.is_active == True)
            ).all()
            assert len(active_rows) == 1
            assert active_rows[0].content == expected_content
