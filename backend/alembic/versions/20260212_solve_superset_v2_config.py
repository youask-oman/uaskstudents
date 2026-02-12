"""seed solve superset v2 active config keys

Revision ID: 20260212_solve_superset_v2
Revises: 20260212_user_tier_std
Create Date: 2026-02-12 23:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260212_solve_superset_v2"
down_revision: Union[str, Sequence[str], None] = "20260212_user_tier_std"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_TIER_POLICY_JSON = (
    '{"FREE":{"min_steps":0,"max_steps":4,"max_tokens":2000,"narrator":false},'
    '"FINAL":{"min_steps":0,"max_steps":2,"max_tokens":2500,"narrator":false},'
    '"STANDARD":{"min_steps":6,"max_steps":12,"max_tokens":5000,"narrator":true},'
    '"RESEARCH":{"min_steps":6,"max_steps":20,"max_tokens":8000,"narrator":true}}'
)


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
    _upsert_system_config("SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2.txt", "Active solve system prompt ID")
    _upsert_system_config(
        "SOLVE_ORCHESTRATOR_DEV_PROMPT_ID",
        "solve_orchestrator_developer_v1.txt",
        "Active solve orchestrator developer prompt ID",
    )
    _upsert_system_config("SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2.txt", "Active solve output contract prompt ID")
    _upsert_system_config("SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2.txt", "Active solve narrator prompt ID")
    _upsert_system_config("SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2.txt", "Active solve plot spec prompt ID")
    _upsert_system_config("SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_v2.txt", "Active solve verification repair prompt ID")
    _upsert_system_config("SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_question_v2.txt", "Active solve clarification prompt ID")
    _upsert_system_config("SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json", "Active solve response schema ID")
    _upsert_system_config("SOLVE_TIER_POLICY_JSON", DEFAULT_TIER_POLICY_JSON, "Solve tier policy JSON")
    _upsert_system_config("SOLVE_NARRATOR_ENABLED", "false", "Enable solve narrator pass")
    _upsert_system_config("SOLVE_V3_USE_SUPERSET_V2", "true", "Use superset v2 solve pipeline for /solve_v3")

    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM prompt_templates WHERE prompt_id = 'solve_clarification_question_v2.txt' LIMIT 1")
    ).fetchone()
    if not exists:
        bind.execute(
            sa.text(
                """
                INSERT INTO prompt_templates
                  (id, prompt_id, tier, mode, role, content, version, is_active, created_at, updated_at, updated_by)
                VALUES
                  (:id, 'solve_clarification_question_v2.txt', NULL, 'SOLVE', 'DEVELOPER', :content, 1, true, NOW(), NOW(), 'alembic:20260212_solve_superset_v2');
                """
            ).bindparams(
                id=str(uuid4()),
                content=(
                    "You are a clarification generator. If the user input appears to contain multiple questions, "
                    "set response_kind=clarification, clarification.needs_clarification=true, and ask at most two concise "
                    "questions to select exactly one problem to solve first. Keep final_answer=null, steps=[]."
                ),
            )
        )


def downgrade() -> None:
    # Keep prompt/schema rows intact; only remove the solve-v2 config keys.
    op.execute(
        """
        DELETE FROM systemconfig
        WHERE key IN (
          'SOLVE_SYSTEM_PROMPT_ID',
          'SOLVE_ORCHESTRATOR_DEV_PROMPT_ID',
          'SOLVE_OUTPUT_CONTRACT_ID',
          'SOLVE_NARRATOR_PROMPT_ID',
          'SOLVE_PLOT_SPEC_PROMPT_ID',
          'SOLVE_REPAIR_PROMPT_ID',
          'SOLVE_CLARIFY_PROMPT_ID',
          'SOLVE_SCHEMA_ID',
          'SOLVE_TIER_POLICY_JSON',
          'SOLVE_NARRATOR_ENABLED',
          'SOLVE_V3_USE_SUPERSET_V2'
        );
        """
    )
