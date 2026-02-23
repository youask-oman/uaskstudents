import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlmodel import Session, select

from app.database import engine
from app.models import (
    JsonSchemaEntry,
    LegalDocument,
    Plan,
    PromptBinding,
    PromptTemplateEntry,
    ProviderModelPricing,
    TopUpProduct,
    SystemConfig,
    User,
    School,
)
from app.models.credit_program_models import CreditProgramDefinition


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "seed_data"


from decimal import Decimal

def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _row_to_dict(row: Any) -> Dict[str, Any]:
    data = {}
    for key, value in row.__dict__.items():
        if key.startswith("_"):
            continue
        data[key] = _jsonable(value)
    return data


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(data: Any) -> str:
    return hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> Tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    # Use atomic replace + retry to avoid intermittent Windows write errors on large files.
    last_err: Exception | None = None
    for _ in range(3):
        tmp_fd = None
        tmp_name = None
        try:
            tmp_fd, tmp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=str(path.parent),
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as fh:
                tmp_fd = None
                fh.write(text)
            os.replace(tmp_name, str(path))
            last_err = None
            break
        except Exception as e:
            last_err = e
            time.sleep(0.2)
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except Exception:
                    pass
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
    if last_err is not None:
        raise last_err
    return (len(payload) if isinstance(payload, list) else 1, _sha256(payload))


def _ordered_systemconfig(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(select(SystemConfig).order_by(SystemConfig.key.asc())).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_json_schemas(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(JsonSchemaEntry).order_by(JsonSchemaEntry.schema_id.asc(), JsonSchemaEntry.version.asc(), JsonSchemaEntry.id.asc())
    ).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_prompt_templates(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(PromptTemplateEntry).order_by(PromptTemplateEntry.prompt_id.asc(), PromptTemplateEntry.version.asc(), PromptTemplateEntry.id.asc())
    ).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_prompt_bindings(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(PromptBinding).order_by(PromptBinding.tier.asc(), PromptBinding.mode.asc(), PromptBinding.created_at.asc(), PromptBinding.id.asc())
    ).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_pricing(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(ProviderModelPricing).order_by(
            ProviderModelPricing.provider.asc(),
            ProviderModelPricing.model.asc(),
            ProviderModelPricing.effective_from.asc(),
            ProviderModelPricing.id.asc(),
        )
    ).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_credit_programs(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(select(CreditProgramDefinition).order_by(CreditProgramDefinition.slug.asc(), CreditProgramDefinition.id.asc())).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_plans(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(select(Plan).order_by(Plan.slug.asc(), Plan.id.asc())).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_schools(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(select(School).order_by(School.country.asc(), School.province_state.asc(), School.city.asc(), School.school_name.asc())).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_internal_users(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(User)
        .where(User.is_internal == True)
        .where(User.email.like("%@uask.ai"))
        .where(User.email != "schema-smoke@uask.ai")
        .order_by(User.email.asc(), User.id.asc())
    ).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_topup_products(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(select(TopUpProduct).order_by(TopUpProduct.code.asc(), TopUpProduct.id.asc())).all()
    return [_row_to_dict(r) for r in rows]


def _ordered_legal_documents(session: Session) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(LegalDocument).order_by(LegalDocument.key.asc(), LegalDocument.version.asc(), LegalDocument.id.asc())
    ).all()
    return [_row_to_dict(r) for r in rows]


def _validate_payloads(
    prompt_templates: List[Dict[str, Any]],
    json_schemas: List[Dict[str, Any]],
    prompt_bindings: List[Dict[str, Any]],
) -> List[str]:
    prompt_ids = {row["prompt_id"] for row in prompt_templates}
    schema_ids = {row["schema_id"] for row in json_schemas}

    missing_system = sorted({row["global_system_prompt_id"] for row in prompt_bindings if row["global_system_prompt_id"] not in prompt_ids})
    missing_developer = sorted({row["developer_prompt_id"] for row in prompt_bindings if row["developer_prompt_id"] not in prompt_ids})
    missing_schema = sorted({row["output_schema_id"] for row in prompt_bindings if row["output_schema_id"] not in schema_ids})

    warnings: List[str] = []
    if missing_system:
        warnings.append(f"missing system prompt_ids in prompt_templates: {missing_system}")
    if missing_developer:
        warnings.append(f"missing developer prompt_ids in prompt_templates: {missing_developer}")
    if missing_schema:
        warnings.append(f"missing output schema_ids in json_schemas: {missing_schema}")
    return warnings


def _filter_seedable_prompt_bindings(
    prompt_templates: List[Dict[str, Any]],
    json_schemas: List[Dict[str, Any]],
    prompt_bindings: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    prompt_ids = {row.get("prompt_id") for row in prompt_templates}
    schema_ids = {row.get("schema_id") for row in json_schemas}
    filtered: List[Dict[str, Any]] = []
    dropped = 0
    for row in prompt_bindings:
        system_id = row.get("global_system_prompt_id")
        dev_id = row.get("developer_prompt_id")
        schema_id = row.get("output_schema_id")
        if system_id in prompt_ids and dev_id in prompt_ids and schema_id in schema_ids:
            filtered.append(row)
        else:
            dropped += 1
    return filtered, dropped


def export_all(out_dir: Path) -> Dict[str, Dict[str, Any]]:
    with Session(engine) as session:
        systemconfig = _ordered_systemconfig(session)
        json_schemas = _ordered_json_schemas(session)
        prompt_templates = _ordered_prompt_templates(session)
        prompt_bindings_all = _ordered_prompt_bindings(session)
        providermodelpricing = _ordered_pricing(session)
        credit_programs = _ordered_credit_programs(session)
        plans = _ordered_plans(session)
        internal_users = _ordered_internal_users(session)
        schools = _ordered_schools(session)
        topup_products = _ordered_topup_products(session)
        legal_documents = _ordered_legal_documents(session)

    validation_warnings = _validate_payloads(prompt_templates, json_schemas, prompt_bindings_all)
    prompt_bindings, dropped_bindings = _filter_seedable_prompt_bindings(
        prompt_templates, json_schemas, prompt_bindings_all
    )
    if dropped_bindings:
        validation_warnings.append(f"dropped_unseedable_prompt_bindings={dropped_bindings}")

    credits_and_plans = {"credit_programs": credit_programs, "plans": plans}

    summary: Dict[str, Dict[str, Any]] = {}

    count, checksum = _write_json(out_dir / "systemconfig.json", systemconfig)
    summary["systemconfig.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "json_schemas.json", json_schemas)
    summary["json_schemas.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "prompt_templates.json", prompt_templates)
    summary["prompt_templates.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "prompt_bindings.json", prompt_bindings)
    summary["prompt_bindings.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "prompt_schema_links.json", [])
    summary["prompt_schema_links.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "providermodelpricing.json", providermodelpricing)
    summary["providermodelpricing.json"] = {"row_count": count, "sha256": checksum}

    cp_count, cp_checksum = _write_json(out_dir / "credit_programs_or_plans.json", credits_and_plans)
    summary["credit_programs_or_plans.json"] = {
        "row_count": len(credit_programs) + len(plans),
        "sha256": cp_checksum,
    }

    count, checksum = _write_json(out_dir / "internal_users.json", internal_users)
    summary["internal_users.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "topup_products.json", topup_products)
    summary["topup_products.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "legal_documents.json", legal_documents)
    summary["legal_documents.json"] = {"row_count": count, "sha256": checksum}

    count, checksum = _write_json(out_dir / "schools.json", schools)
    summary["schools.json"] = {"row_count": count, "sha256": checksum}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_warnings": validation_warnings,
        "schema_table_map": {
            "schema_tables": ["json_schemas"],
            "prompt_binding_reference_model": "key-based strings",
            "prompt_bindings_to_prompts": ["global_system_prompt_id -> prompt_templates.prompt_id", "developer_prompt_id -> prompt_templates.prompt_id"],
            "prompt_bindings_to_schema": "output_schema_id -> json_schemas.schema_id",
            "link_tables": [],
        },
        "files": summary,
    }
    _write_json(out_dir / "seed_manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deterministic prompt/schema and core seed datasets.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for seed json files.")
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    summary = export_all(out_dir)
    print("Export completed:")
    for name in sorted(summary.keys()):
        meta = summary[name]
        print(f"  {name}: rows={meta['row_count']} sha256={meta['sha256']}")


if __name__ == "__main__":
    main()
