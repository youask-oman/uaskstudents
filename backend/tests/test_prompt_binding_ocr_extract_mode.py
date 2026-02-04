from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PromptBinding,
    PromptModeEnum,
    PromptRoleEnum,
    PromptTierEnum,
)
from app.services.prompt_registry_service import prompt_registry_service


def _make_session(tmp_path) -> Session:
    db_path = tmp_path / "binding_mode.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_prompt(
    *,
    session: Session,
    prompt_id: str,
    mode: PromptModeEnum,
    role: PromptRoleEnum,
    tier: PromptTierEnum | None = None,
) -> None:
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id=prompt_id,
        content=f"content::{prompt_id}",
        tier=tier,
        mode=mode,
        role=role,
        updated_by="test",
    )


def _seed_schema(*, session: Session, schema_id: str) -> None:
    prompt_registry_service.update_schema(
        session=session,
        schema_id=schema_id,
        content={"type": "object", "title": schema_id},
        updated_by="test",
    )


def test_ocr_extract_binding_is_independent_from_solve_binding(tmp_path):
    session = _make_session(tmp_path)

    _seed_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        tier=None,
    )
    _seed_prompt(
        session=session,
        prompt_id="solve_standard_v1",
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        tier=PromptTierEnum.STANDARD,
    )
    _seed_prompt(
        session=session,
        prompt_id="ocr_extract_developer_v1",
        mode=PromptModeEnum.OCR_EXTRACT,
        role=PromptRoleEnum.DEVELOPER,
        tier=PromptTierEnum.STANDARD,
    )
    _seed_prompt(
        session=session,
        prompt_id="ocr_extract_developer_v2",
        mode=PromptModeEnum.OCR_EXTRACT,
        role=PromptRoleEnum.DEVELOPER,
        tier=PromptTierEnum.STANDARD,
    )
    _seed_schema(session=session, schema_id="solve_schema_v1")
    _seed_schema(session=session, schema_id="ocr_extract_schema_v1")
    _seed_schema(session=session, schema_id="ocr_extract_schema_v2")

    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="solve_standard_v1",
        output_schema_id="solve_schema_v1",
        updated_by="test",
    )
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.OCR_EXTRACT,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="ocr_extract_developer_v1",
        output_schema_id="ocr_extract_schema_v1",
        updated_by="test",
    )

    active_solve = prompt_registry_service.get_active_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
    )
    active_ocr = prompt_registry_service.get_active_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.OCR_EXTRACT,
    )
    assert active_solve is not None
    assert active_ocr is not None
    assert active_solve.developer_prompt_id == "solve_standard_v1"
    assert active_ocr.developer_prompt_id == "ocr_extract_developer_v1"

    # Re-activating OCR_EXTRACT deactivates prior OCR binding only.
    prompt_registry_service.activate_binding(
        session=session,
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.OCR_EXTRACT,
        global_system_prompt_id="global_system_prompt_v1",
        developer_prompt_id="ocr_extract_developer_v2",
        output_schema_id="ocr_extract_schema_v2",
        updated_by="test",
    )

    active_solve_after = prompt_registry_service.get_active_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
    )
    active_ocr_after = prompt_registry_service.get_active_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.OCR_EXTRACT,
    )
    assert active_solve_after is not None
    assert active_solve_after.developer_prompt_id == "solve_standard_v1"
    assert active_ocr_after is not None
    assert active_ocr_after.developer_prompt_id == "ocr_extract_developer_v2"

    active_rows = session.exec(
        select(PromptBinding)
        .where(PromptBinding.tier == PromptTierEnum.STANDARD)
        .where(PromptBinding.is_active == True)
    ).all()
    assert len(active_rows) == 2


def test_all_modes_keep_separate_active_bindings_per_tier(tmp_path):
    session = _make_session(tmp_path)
    tier = PromptTierEnum.STANDARD
    modes = [
        PromptModeEnum.SOLVE,
        PromptModeEnum.OCR_EXTRACT,
        PromptModeEnum.VERIFY,
        PromptModeEnum.PLOT_TRIGGER,
        PromptModeEnum.PLOT_SPEC,
    ]

    _seed_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        tier=None,
    )

    for mode in modes:
        mode_id = mode.value.lower()
        _seed_prompt(
            session=session,
            prompt_id=f"dev_{mode_id}_v1",
            mode=mode,
            role=PromptRoleEnum.DEVELOPER,
            tier=tier,
        )
        _seed_schema(session=session, schema_id=f"schema_{mode_id}_v1")
        prompt_registry_service.activate_binding(
            session=session,
            tier=tier,
            mode=mode,
            global_system_prompt_id="global_system_prompt_v1",
            developer_prompt_id=f"dev_{mode_id}_v1",
            output_schema_id=f"schema_{mode_id}_v1",
            updated_by="test",
        )

    active_rows = session.exec(
        select(PromptBinding)
        .where(PromptBinding.tier == tier)
        .where(PromptBinding.is_active == True)
    ).all()
    assert len(active_rows) == len(modes)

    for mode in modes:
        binding = prompt_registry_service.get_active_binding(session, tier, mode)
        assert binding is not None
        mode_id = mode.value.lower()
        assert binding.developer_prompt_id == f"dev_{mode_id}_v1"
        assert binding.output_schema_id == f"schema_{mode_id}_v1"
