import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import PromptTierEnum, PromptModeEnum, PromptRoleEnum
from app.services.prompt_registry_service import prompt_registry_service
from app.services.prompt_manager import prompt_manager


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "manager.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def seed_prompt(session, prompt_id, tier, mode, role, content):
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id=prompt_id,
        content=content,
        tier=tier,
        mode=mode,
        role=role,
        updated_by="tester",
    )


def seed_schema(session, schema_id):
    prompt_registry_service.update_schema(
        session=session,
        schema_id=schema_id,
        content={"type": "object"},
        updated_by="tester",
    )


def test_prompt_selection_map(session):
    seed_prompt(session, "global_system_prompt_v1", None, PromptModeEnum.SOLVE, PromptRoleEnum.SYSTEM, "sys")
    seed_prompt(session, "solve_free_minimal_v1", PromptTierEnum.FREE, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "free")
    seed_prompt(session, "solve_standard_extreme_detailed_v1", PromptTierEnum.STANDARD, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "std")
    seed_prompt(session, "solve_research_v1", PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER, "res")
    seed_prompt(session, "verify_v1", None, PromptModeEnum.VERIFY, PromptRoleEnum.DEVELOPER, "verify")
    seed_prompt(session, "plot_trigger_v1", None, PromptModeEnum.PLOT_TRIGGER, PromptRoleEnum.DEVELOPER, "plot_trigger")
    seed_prompt(session, "plot_spec_v1", None, PromptModeEnum.PLOT_SPEC, PromptRoleEnum.DEVELOPER, "plot_spec")

    seed_schema(session, "youask_math_solver_response_v1")
    seed_schema(session, "youask_math_solver_standard_solve_extreme_v1")
    seed_schema(session, "youask_math_solver_research_solve_v1")
    seed_schema(session, "youask_math_solver_verify_v1")
    seed_schema(session, "youask_plot_trigger_v1")
    seed_schema(session, "youask_plot_spec_v1")

    prompt_registry_service.activate_binding(
        session, PromptTierEnum.FREE, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_free_minimal_v1", "youask_math_solver_response_v1", "tester"
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_standard_extreme_detailed_v1",
        "youask_math_solver_standard_solve_extreme_v1",
        "tester",
    )
    prompt_registry_service.activate_binding(
        session, PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_research_v1", "youask_math_solver_research_solve_v1", "tester"
    )
    prompt_registry_service.activate_binding(
        session, PromptTierEnum.FREE, PromptModeEnum.VERIFY, "global_system_prompt_v1", "verify_v1", "youask_math_solver_verify_v1", "tester"
    )
    prompt_registry_service.activate_binding(
        session, PromptTierEnum.FREE, PromptModeEnum.PLOT_TRIGGER, "global_system_prompt_v1", "plot_trigger_v1", "youask_plot_trigger_v1", "tester"
    )
    prompt_registry_service.activate_binding(
        session, PromptTierEnum.FREE, PromptModeEnum.PLOT_SPEC, "global_system_prompt_v1", "plot_spec_v1", "youask_plot_spec_v1", "tester"
    )

    free = prompt_manager.get_binding(session, PromptTierEnum.FREE, PromptModeEnum.SOLVE)
    assert free["schema"]["type"] == "object"
    assert "free" in free["developer_prompt"]

    standard = prompt_manager.get_binding(session, PromptTierEnum.STANDARD, PromptModeEnum.SOLVE)
    assert "std" in standard["developer_prompt"]

    research = prompt_manager.get_binding(session, PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE)
    assert "res" in research["developer_prompt"]

    verify = prompt_manager.get_binding(session, PromptTierEnum.FREE, PromptModeEnum.VERIFY)
    assert "verify" in verify["developer_prompt"]

    plot_trigger = prompt_manager.get_binding(session, PromptTierEnum.FREE, PromptModeEnum.PLOT_TRIGGER)
    assert "plot_trigger" in plot_trigger["developer_prompt"]

    plot_spec = prompt_manager.get_binding(session, PromptTierEnum.FREE, PromptModeEnum.PLOT_SPEC)
    assert "plot_spec" in plot_spec["developer_prompt"]
