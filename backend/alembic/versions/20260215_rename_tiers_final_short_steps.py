"""rename solve tiers FREE->SHORT_STEPS and SHORT->FINAL

Revision ID: 20260215_rename_tiers
Revises: 20260215_drop_binding_ck
Create Date: 2026-02-15
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260215_rename_tiers"
down_revision: Union[str, None] = "20260215_drop_binding_ck"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _remap_json_keys(payload: dict, forward: bool) -> dict:
    if not isinstance(payload, dict):
        return payload
    data = dict(payload)
    credits = data.get("credits")
    if not isinstance(credits, dict):
        return data

    def _remap_map_keys(obj: dict) -> dict:
        if not isinstance(obj, dict):
            return obj
        out = dict(obj)
        if forward:
            if "free" in out and "short_steps" not in out:
                out["short_steps"] = out["free"]
            if "short" in out and "final" not in out:
                out["final"] = out["short"]
            out.pop("free", None)
            out.pop("short", None)
        else:
            if "short_steps" in out and "free" not in out:
                out["free"] = out["short_steps"]
            if "final" in out and "short" not in out:
                out["short"] = out["final"]
            out.pop("short_steps", None)
            out.pop("final", None)
        return out

    for section in ("solve", "verify", "attempt_fee"):
        section_obj = credits.get(section)
        if isinstance(section_obj, dict):
            credits[section] = _remap_map_keys(section_obj)

    data["credits"] = credits
    return data


def _rewrite_prompt_binding_multipliers(conn: sa.engine.Connection, forward: bool) -> None:
    rows = conn.execute(sa.text("SELECT id, multipliers FROM prompt_bindings")).mappings().all()
    for row in rows:
        multipliers = row.get("multipliers")
        if isinstance(multipliers, str):
            try:
                multipliers = json.loads(multipliers)
            except Exception:
                continue
        if not isinstance(multipliers, dict):
            continue
        remapped = _remap_json_keys(multipliers, forward=forward)
        conn.execute(
            sa.text("UPDATE prompt_bindings SET multipliers = :payload WHERE id = :id"),
            {"id": row["id"], "payload": json.dumps(remapped)},
        )


def _rewrite_tier_policy_json(conn: sa.engine.Connection, forward: bool) -> None:
    row = conn.execute(
        sa.text("SELECT value FROM systemconfig WHERE key = 'SOLVE_TIER_POLICY_JSON'")
    ).first()
    if not row or not row[0]:
        return
    try:
        payload = json.loads(row[0])
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    new_payload = dict(payload)
    if forward:
        if "FREE" in new_payload and "SHORT_STEPS" not in new_payload:
            new_payload["SHORT_STEPS"] = new_payload["FREE"]
        if "SHORT" in new_payload and "FINAL" not in new_payload:
            new_payload["FINAL"] = new_payload["SHORT"]
        new_payload.pop("FREE", None)
        new_payload.pop("SHORT", None)
    else:
        if "SHORT_STEPS" in new_payload and "FREE" not in new_payload:
            new_payload["FREE"] = new_payload["SHORT_STEPS"]
        if "FINAL" in new_payload and "SHORT" not in new_payload:
            new_payload["SHORT"] = new_payload["FINAL"]
        new_payload.pop("SHORT_STEPS", None)
        new_payload.pop("FINAL", None)

    conn.execute(
        sa.text("UPDATE systemconfig SET value = :value WHERE key = 'SOLVE_TIER_POLICY_JSON'"),
        {"value": json.dumps(new_payload)},
    )


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        context = op.get_context()
        with context.autocommit_block():
            op.execute("ALTER TYPE prompttierenum ADD VALUE IF NOT EXISTS 'FINAL'")
            op.execute("ALTER TYPE prompttierenum ADD VALUE IF NOT EXISTS 'SHORT_STEPS'")
        op.execute("UPDATE prompt_bindings SET tier = 'FINAL' WHERE tier::text = 'SHORT'")
        op.execute("UPDATE prompt_bindings SET tier = 'SHORT_STEPS' WHERE tier::text = 'FREE'")
        op.execute("UPDATE prompt_templates SET tier = 'FINAL' WHERE tier::text = 'SHORT'")
        op.execute("UPDATE prompt_templates SET tier = 'SHORT_STEPS' WHERE tier::text = 'FREE'")
    else:
        op.execute("UPDATE prompt_bindings SET tier = 'FINAL' WHERE tier = 'SHORT'")
        op.execute("UPDATE prompt_bindings SET tier = 'SHORT_STEPS' WHERE tier = 'FREE'")
        op.execute("UPDATE prompt_templates SET tier = 'FINAL' WHERE tier = 'SHORT'")
        op.execute("UPDATE prompt_templates SET tier = 'SHORT_STEPS' WHERE tier = 'FREE'")

    op.execute(
        """
        UPDATE "user"
        SET subscription_tier = CASE
            WHEN lower(subscription_tier) = 'free' THEN 'short_steps'
            WHEN lower(subscription_tier) = 'short' THEN 'final'
            WHEN lower(subscription_tier) = 'family_standard' THEN 'final'
            ELSE subscription_tier
        END
        """
    )
    op.execute(
        """
        UPDATE chatsession
        SET solve_tier = CASE
            WHEN lower(solve_tier) = 'free' THEN 'short_steps'
            WHEN lower(solve_tier) = 'short' THEN 'final'
            ELSE solve_tier
        END
        """
    )
    op.execute(
        """
        UPDATE billingledger
        SET tier = CASE
            WHEN upper(tier) = 'FREE' THEN 'SHORT_STEPS'
            WHEN upper(tier) = 'SHORT' THEN 'FINAL'
            ELSE tier
        END
        """
    )
    op.execute(
        """
        UPDATE credit_holds
        SET tier = CASE
            WHEN upper(tier) = 'FREE' THEN 'SHORT_STEPS'
            WHEN upper(tier) = 'SHORT' THEN 'FINAL'
            ELSE tier
        END
        """
    )
    op.execute(
        """
        UPDATE usage_ledger
        SET tier = CASE
            WHEN upper(tier) = 'FREE' THEN 'SHORT_STEPS'
            WHEN upper(tier) = 'SHORT' THEN 'FINAL'
            ELSE tier
        END
        """
    )

    _rewrite_prompt_binding_multipliers(conn, forward=True)
    _rewrite_tier_policy_json(conn, forward=True)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.execute("UPDATE prompt_bindings SET tier = 'SHORT' WHERE tier::text = 'FINAL'")
        op.execute("UPDATE prompt_bindings SET tier = 'FREE' WHERE tier::text = 'SHORT_STEPS'")
        op.execute("UPDATE prompt_templates SET tier = 'SHORT' WHERE tier::text = 'FINAL'")
        op.execute("UPDATE prompt_templates SET tier = 'FREE' WHERE tier::text = 'SHORT_STEPS'")
    else:
        op.execute("UPDATE prompt_bindings SET tier = 'SHORT' WHERE tier = 'FINAL'")
        op.execute("UPDATE prompt_bindings SET tier = 'FREE' WHERE tier = 'SHORT_STEPS'")
        op.execute("UPDATE prompt_templates SET tier = 'SHORT' WHERE tier = 'FINAL'")
        op.execute("UPDATE prompt_templates SET tier = 'FREE' WHERE tier = 'SHORT_STEPS'")

    op.execute(
        """
        UPDATE "user"
        SET subscription_tier = CASE
            WHEN lower(subscription_tier) = 'short_steps' THEN 'free'
            WHEN lower(subscription_tier) = 'final' THEN 'short'
            ELSE subscription_tier
        END
        """
    )
    op.execute(
        """
        UPDATE chatsession
        SET solve_tier = CASE
            WHEN lower(solve_tier) = 'short_steps' THEN 'free'
            WHEN lower(solve_tier) = 'final' THEN 'short'
            ELSE solve_tier
        END
        """
    )
    op.execute(
        """
        UPDATE billingledger
        SET tier = CASE
            WHEN upper(tier) = 'SHORT_STEPS' THEN 'FREE'
            WHEN upper(tier) = 'FINAL' THEN 'SHORT'
            ELSE tier
        END
        """
    )
    op.execute(
        """
        UPDATE credit_holds
        SET tier = CASE
            WHEN upper(tier) = 'SHORT_STEPS' THEN 'FREE'
            WHEN upper(tier) = 'FINAL' THEN 'SHORT'
            ELSE tier
        END
        """
    )
    op.execute(
        """
        UPDATE usage_ledger
        SET tier = CASE
            WHEN upper(tier) = 'SHORT_STEPS' THEN 'FREE'
            WHEN upper(tier) = 'FINAL' THEN 'SHORT'
            ELSE tier
        END
        """
    )

    _rewrite_prompt_binding_multipliers(conn, forward=False)
    _rewrite_tier_policy_json(conn, forward=False)
