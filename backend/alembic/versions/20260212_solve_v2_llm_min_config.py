"""switch solve v2 config to compact prompts and patch schemas

Revision ID: 20260212_solve_v2_llm_min
Revises: 20260212_act_stream_bind
Create Date: 2026-02-12 12:35:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260212_solve_v2_llm_min"
down_revision: Union[str, Sequence[str], None] = "20260212_act_stream_bind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upsert_system_config(key: str, value: str, description: str) -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO systemconfig (key, value, description, updated_at)
            VALUES (:key, :value, :description, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                description = EXCLUDED.description,
                updated_at = NOW();
            """
        ).bindparams(key=key, value=value, description=description)
    )


def upgrade() -> None:
    _upsert_system_config("SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2_compact.txt", "Active solve system prompt ID")
    _upsert_system_config(
        "SOLVE_ORCHESTRATOR_DEV_PROMPT_ID",
        "solve_orchestrator_developer_v2_compact.txt",
        "Active solve orchestrator developer prompt ID",
    )
    _upsert_system_config("SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2_compact.txt", "Legacy output contract prompt ID (unused by solve_v3)")
    _upsert_system_config("SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2_compact.txt", "Active solve narrator prompt ID")
    _upsert_system_config("SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2_compact.txt", "Active solve plot spec prompt ID")
    _upsert_system_config("SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_patch_v1.txt", "Active solve verification-repair prompt ID")
    _upsert_system_config("SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_patch_v1.txt", "Active solve clarification prompt ID")
    _upsert_system_config("SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json", "Active solve internal response schema ID")
    _upsert_system_config("SOLVE_LLM_MIN_SCHEMA_ID", "solve_llm_min_v2.schema.json", "Active solve main OpenAI response schema ID")
    _upsert_system_config("SOLVE_CLARIFY_SCHEMA_ID", "solve_clarification_patch_v1.schema.json", "Active solve clarification OpenAI response schema ID")
    _upsert_system_config("SOLVE_REPAIR_SCHEMA_ID", "solve_repair_patch_v1.schema.json", "Active solve repair OpenAI response schema ID")


def downgrade() -> None:
    _upsert_system_config("SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2.txt", "Active solve system prompt ID")
    _upsert_system_config("SOLVE_ORCHESTRATOR_DEV_PROMPT_ID", "solve_orchestrator_developer_v1.txt", "Active solve orchestrator developer prompt ID")
    _upsert_system_config("SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2.txt", "Active solve output contract prompt ID")
    _upsert_system_config("SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2.txt", "Active solve narrator prompt ID")
    _upsert_system_config("SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2.txt", "Active solve plot spec prompt ID")
    _upsert_system_config("SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_v2.txt", "Active solve verification-repair prompt ID")
    _upsert_system_config("SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_question_v2.txt", "Active solve clarification prompt ID")
    op.execute(
        """
        DELETE FROM systemconfig
        WHERE key IN ('SOLVE_LLM_MIN_SCHEMA_ID', 'SOLVE_CLARIFY_SCHEMA_ID', 'SOLVE_REPAIR_SCHEMA_ID');
        """
    )

