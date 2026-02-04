import json
import os
import sys
from pathlib import Path

from sqlmodel import Session, create_engine, SQLModel

ROOT = Path(__file__).parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.append(str(BACKEND_DIR))

from app.models import PromptTierEnum, PromptModeEnum, PromptRoleEnum
from app.services.prompt_registry_service import prompt_registry_service


DEFAULT_SOURCE = ROOT / "static_design" / "sug_prompts_openai"
DEPRECATED_PROMPT_IDS = {"solve_standard_moderate_v1", "solve_standard_moderate_v2"}
DEPRECATED_SCHEMA_IDS = {"youask_math_solver_standard_solve_v1", "youask_math_solver_standard_solve_v2"}


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt_meta(prompt_id: str):
    if prompt_id.startswith("global_system"):
        return None, PromptModeEnum.SOLVE, PromptRoleEnum.SYSTEM
    if prompt_id.startswith("solve_free"):
        return PromptTierEnum.FREE, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER
    if prompt_id.startswith("solve_standard"):
        return PromptTierEnum.STANDARD, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER
    if prompt_id.startswith("solve_research"):
        return PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER
    if prompt_id.startswith("verify"):
        return None, PromptModeEnum.VERIFY, PromptRoleEnum.DEVELOPER
    if prompt_id.startswith("plot_trigger"):
        return None, PromptModeEnum.PLOT_TRIGGER, PromptRoleEnum.DEVELOPER
    if prompt_id.startswith("plot_spec"):
        return None, PromptModeEnum.PLOT_SPEC, PromptRoleEnum.DEVELOPER
    return None, PromptModeEnum.SOLVE, PromptRoleEnum.DEVELOPER


def run_import(source_dir: Path, updated_by: str = "import_script"):
    database_url = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(database_url)
    SQLModel.metadata.create_all(engine)

    prompts = []
    schemas = []

    for item in source_dir.iterdir():
        if item.suffix.lower() == ".txt":
            prompts.append(item)
        elif item.suffix.lower() == ".json":
            schemas.append(item)

    with Session(engine) as session:
        print(f"Importing from {source_dir}...")

        for path in prompts:
            prompt_id = path.stem
            if prompt_id in DEPRECATED_PROMPT_IDS:
                continue
            tier, mode, role = _prompt_meta(prompt_id)
            content = _load_text(path)
            entry = prompt_registry_service.update_prompt(
                session=session,
                prompt_id=prompt_id,
                content=content,
                tier=tier,
                mode=mode,
                role=role,
                updated_by=updated_by,
            )
            print(f"[prompt] {prompt_id} -> v{entry.version} active={entry.is_active}")

        for path in schemas:
            schema_id = path.stem
            if schema_id in DEPRECATED_SCHEMA_IDS:
                continue
            content = _load_json(path)
            error = prompt_registry_service.validate_schema(content)
            if error:
                print(f"[schema-warning] {schema_id}: {error}")
            entry = prompt_registry_service.update_schema(
                session=session,
                schema_id=schema_id,
                content=content,
                updated_by=updated_by,
            )
            print(f"[schema] {schema_id} -> v{entry.version} active={entry.is_active}")

        # Bindings
        bindings = [
            (PromptTierEnum.FREE, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_free_minimal_v1", "youask_math_solver_response_v1"),
            (
                PromptTierEnum.STANDARD,
                PromptModeEnum.SOLVE,
                "global_system_prompt_v1",
                "solve_standard_extreme_detailed_v1",
                "youask_math_solver_standard_solve_extreme_v1",
            ),
            (PromptTierEnum.RESEARCH, PromptModeEnum.SOLVE, "global_system_prompt_v1", "solve_research_v1", "youask_math_solver_research_solve_v1"),
            (PromptTierEnum.FREE, PromptModeEnum.VERIFY, "global_system_prompt_v1", "verify_v1", "youask_math_solver_verify_v1"),
            (PromptTierEnum.STANDARD, PromptModeEnum.VERIFY, "global_system_prompt_v1", "verify_v1", "youask_math_solver_verify_v1"),
            (PromptTierEnum.RESEARCH, PromptModeEnum.VERIFY, "global_system_prompt_v1", "verify_v1", "youask_math_solver_verify_v1"),
            (PromptTierEnum.FREE, PromptModeEnum.PLOT_TRIGGER, "global_system_prompt_v1", "plot_trigger_v1", "youask_plot_trigger_v1"),
            (PromptTierEnum.STANDARD, PromptModeEnum.PLOT_TRIGGER, "global_system_prompt_v1", "plot_trigger_v1", "youask_plot_trigger_v1"),
            (PromptTierEnum.RESEARCH, PromptModeEnum.PLOT_TRIGGER, "global_system_prompt_v1", "plot_trigger_v1", "youask_plot_trigger_v1"),
            (PromptTierEnum.FREE, PromptModeEnum.PLOT_SPEC, "global_system_prompt_v1", "plot_spec_v1", "youask_plot_spec_v1"),
            (PromptTierEnum.STANDARD, PromptModeEnum.PLOT_SPEC, "global_system_prompt_v1", "plot_spec_v1", "youask_plot_spec_v1"),
            (PromptTierEnum.RESEARCH, PromptModeEnum.PLOT_SPEC, "global_system_prompt_v1", "plot_spec_v1", "youask_plot_spec_v1"),
        ]
        for tier, mode, global_id, dev_id, schema_id in bindings:
            binding = prompt_registry_service.activate_binding(
                session=session,
                tier=tier,
                mode=mode,
                global_system_prompt_id=global_id,
                developer_prompt_id=dev_id,
                output_schema_id=schema_id,
                updated_by=updated_by,
            )
            print(f"[binding] {tier.value}/{mode.value} -> {binding.global_system_prompt_id} + {binding.developer_prompt_id} => {binding.output_schema_id}")

        prompt_registry_service.ensure_standard_solve_binding(session, updated_by=updated_by)


if __name__ == "__main__":
    run_import(DEFAULT_SOURCE)
