import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session, SQLModel, create_engine, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PromptModeEnum, PromptRoleEnum, PromptTemplateEntry, PromptTierEnum  # noqa: E402


@dataclass(frozen=True)
class PromptAssetTarget:
    prompt_id: str
    tier: PromptTierEnum
    asset_path: Path


DEFAULT_TARGETS: List[PromptAssetTarget] = [
    PromptAssetTarget(
        prompt_id="free_form_math_free_fast_v1",
        tier=PromptTierEnum.FREE,
        asset_path=REPO_ROOT / "static_design" / "sug_prompts_qwen" / "free_form_math_free_fast_v1.txt",
    ),
    PromptAssetTarget(
        prompt_id="free_form_math_standard_detailed_v1",
        tier=PromptTierEnum.STANDARD,
        asset_path=REPO_ROOT / "static_design" / "sug_prompts_qwen" / "free_form_math_standard_detailed.txt",
    ),
    PromptAssetTarget(
        prompt_id="free_form_math_research_rigorous_v1",
        tier=PromptTierEnum.RESEARCH,
        asset_path=REPO_ROOT / "static_design" / "sug_prompts_qwen" / "free_form_math_research_rigorous_v1.txt",
    ),
]


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_asset_content(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt asset: {path}")
    return path.read_text(encoding="utf-8")


def _build_engine(database_url: Optional[str]):
    resolved = (database_url or os.environ.get("DATABASE_URL") or "postgresql://uask_user:uask_password@localhost:5432/uask_db").strip()
    if resolved.startswith("postgres://"):
        resolved = resolved.replace("postgres://", "postgresql://", 1)
    return create_engine(resolved), resolved


def _sort_rows(rows: List[PromptTemplateEntry]) -> List[PromptTemplateEntry]:
    return sorted(rows, key=lambda row: (row.version, row.created_at, row.id), reverse=True)


def sync_freeform_prompt_templates(
    *,
    database_url: Optional[str] = None,
    updated_by: str = "sync_freeform_prompt_templates",
) -> Dict[str, Any]:
    engine, resolved_db_url = _build_engine(database_url)
    SQLModel.metadata.create_all(engine)

    changed: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []

    with Session(engine) as session:
        with session.begin():
            for target in DEFAULT_TARGETS:
                content = _load_asset_content(target.asset_path)
                if "{PROBLEM}" not in content:
                    raise ValueError(
                        f"Prompt {target.prompt_id} is missing required placeholder {{PROBLEM}}."
                    )

                existing_rows = session.exec(
                    select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == target.prompt_id)
                ).all()
                sorted_rows = _sort_rows(list(existing_rows))
                active_rows = [row for row in sorted_rows if row.is_active]
                active_primary = active_rows[0] if active_rows else None

                for duplicate in active_rows[1:]:
                    duplicate.is_active = False
                    duplicate.updated_at = datetime.utcnow()
                    duplicate.updated_by = updated_by
                    session.add(duplicate)

                current_matches_target = bool(
                    active_primary
                    and active_primary.content == content
                    and active_primary.tier == target.tier
                    and active_primary.mode == PromptModeEnum.SOLVE
                    and active_primary.role == PromptRoleEnum.DEVELOPER
                )

                if current_matches_target:
                    unchanged.append(
                        {
                            "prompt_id": target.prompt_id,
                            "tier": target.tier.value,
                            "provider": "ollama",
                            "mode": PromptModeEnum.SOLVE.value,
                            "version": active_primary.version,
                            "row_id": active_primary.id,
                            "checksum": _checksum(content),
                        }
                    )
                    continue

                for active in active_rows:
                    active.is_active = False
                    active.updated_at = datetime.utcnow()
                    active.updated_by = updated_by
                    session.add(active)

                next_version = max((row.version for row in sorted_rows), default=0) + 1
                entry = PromptTemplateEntry(
                    prompt_id=target.prompt_id,
                    tier=target.tier,
                    mode=PromptModeEnum.SOLVE,
                    role=PromptRoleEnum.DEVELOPER,
                    content=content,
                    version=next_version,
                    is_active=True,
                    updated_by=updated_by,
                )
                session.add(entry)
                session.flush()

                changed.append(
                    {
                        "prompt_id": entry.prompt_id,
                        "tier": entry.tier.value if entry.tier else None,
                        "provider": "ollama",
                        "mode": entry.mode.value if entry.mode else None,
                        "version": entry.version,
                        "row_id": entry.id,
                        "checksum": _checksum(content),
                        "asset_path": str(target.asset_path.relative_to(REPO_ROOT)),
                    }
                )

    with Session(engine) as session:
        active_rows = []
        for target in DEFAULT_TARGETS:
            row = session.exec(
                select(PromptTemplateEntry)
                .where(PromptTemplateEntry.prompt_id == target.prompt_id)
                .where(PromptTemplateEntry.is_active == True)
                .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
            ).first()
            if row:
                active_rows.append(
                    {
                        "prompt_id": row.prompt_id,
                        "tier": row.tier.value if row.tier else None,
                        "provider": "ollama",
                        "mode": row.mode.value if row.mode else None,
                        "role": row.role.value if row.role else None,
                        "version": row.version,
                        "row_id": row.id,
                        "updated_at": row.updated_at.isoformat(),
                        "updated_by": row.updated_by,
                    }
                )

    return {
        "database_url": resolved_db_url,
        "updated_by": updated_by,
        "changed_count": len(changed),
        "unchanged_count": len(unchanged),
        "changed": changed,
        "unchanged": unchanged,
        "active_rows": active_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync FREE/STANDARD/RESEARCH free-form prompt_templates from approved prompt asset files."
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL for this run.")
    parser.add_argument("--updated-by", default="sync_freeform_prompt_templates", help="Audit tag for updated_by.")
    args = parser.parse_args()

    report = sync_freeform_prompt_templates(database_url=args.database_url, updated_by=args.updated_by)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
