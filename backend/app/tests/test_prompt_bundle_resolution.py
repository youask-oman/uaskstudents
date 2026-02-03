import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import PromptModeEnum, PromptRoleEnum, PromptTierEnum
from app.prompts.db_loader import PromptBindingLookupError, invalidate_cache, resolve_prompt_bundle
from app.services.prompt_registry_service import prompt_registry_service


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "prompt_bundle_resolution.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def _clear_prompt_bundle_cache():
    invalidate_cache()


def _seed_base_system_and_schema(session: Session, schema_id: str) -> None:
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="global_system_prompt_v1",
        content="SYSTEM_PROMPT",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.SYSTEM,
        updated_by="tester",
    )
    prompt_registry_service.update_schema(
        session=session,
        schema_id=schema_id,
        content={"type": "object", "properties": {"final_answer": {"type": "string"}}},
        updated_by="tester",
    )


def test_resolve_prompt_bundle_standard_solve_prefers_standard_template(session: Session):
    _seed_base_system_and_schema(session, "youask_math_solver_standard_solve_v1")
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_v1",
        content="STANDARD_DEVELOPER_PROMPT",
        tier=PromptTierEnum.STANDARD,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_standard_v1",
        "youask_math_solver_standard_solve_v1",
        "tester",
    )

    bundle = resolve_prompt_bundle(
        provider="ollama",
        tier="STANDARD",
        mode="SOLVE",
        db_session=session,
    )
    assert bundle.developer_prompt_id == "solve_standard_v1"
    assert bundle.developer_prompt_content == "STANDARD_DEVELOPER_PROMPT"
    assert bundle.output_schema_id == "youask_math_solver_standard_solve_v1"


def test_resolve_prompt_bundle_research_solve_uses_research_ids(session: Session):
    _seed_base_system_and_schema(session, "youask_math_solver_research_solve_v1")
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_research_v1",
        content="RESEARCH_DEVELOPER_PROMPT",
        tier=PromptTierEnum.RESEARCH,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.RESEARCH,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_research_v1",
        "youask_math_solver_research_solve_v1",
        "tester",
    )

    bundle = resolve_prompt_bundle(
        provider="ollama",
        tier="RESEARCH",
        mode="SOLVE",
        db_session=session,
    )
    assert bundle.developer_prompt_id == "solve_research_v1"
    assert bundle.output_schema_id == "youask_math_solver_research_solve_v1"
    assert bundle.template_versions["developer"] is not None


def test_resolve_prompt_bundle_missing_binding_returns_structured_error(session: Session):
    with pytest.raises(PromptBindingLookupError) as exc:
        resolve_prompt_bundle(provider="ollama", tier="STANDARD", mode="SOLVE", db_session=session)
    assert exc.value.code == "PROMPT_BINDING_NOT_FOUND"


def test_resolve_prompt_bundle_solve_requires_tier_specific_developer_template(session: Session):
    _seed_base_system_and_schema(session, "youask_math_solver_standard_solve_v1")
    prompt_registry_service.update_prompt(
        session=session,
        prompt_id="solve_standard_v1",
        content="NULL_TIER_DEVELOPER_PROMPT",
        tier=None,
        mode=PromptModeEnum.SOLVE,
        role=PromptRoleEnum.DEVELOPER,
        updated_by="tester",
    )
    prompt_registry_service.activate_binding(
        session,
        PromptTierEnum.STANDARD,
        PromptModeEnum.SOLVE,
        "global_system_prompt_v1",
        "solve_standard_v1",
        "youask_math_solver_standard_solve_v1",
        "tester",
    )

    with pytest.raises(PromptBindingLookupError) as exc:
        resolve_prompt_bundle(
            provider="ollama",
            tier="STANDARD",
            mode="SOLVE",
            db_session=session,
        )
    assert exc.value.code == "PROMPT_TEMPLATE_TIER_MISSING"
