import argparse
import hashlib
import json
import os
import sqlalchemy as sa
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select
from sqlalchemy import text

from app.database import engine
from app.auth import get_password_hash
from app.models import (
    CreditTransfer,
    CreditLot,
    JsonSchemaEntry,
    Notification,
    Payment,
    Plan,
    LegalDocument,
    PromptBinding,
    PromptModeEnum,
    PromptRoleEnum,
    PromptTemplateEntry,
    PromptTierEnum,
    ProviderModelPricing,
    School,
    SeedRegistry,
    SystemConfig,
    TopUpProduct,
    TrimStrategyEnum,
    User,
)
from app.models.credit_program_models import CreditProgramDefinition
from app.services.legal_document_renderer import markdown_to_basic_html
from app.services.privacy_policy_generator import build_privacy_policy_markdown
from app.services.school_import_service import import_school_csvs


ROOT = Path(__file__).resolve().parents[1]
SEED_DATA_DIR = ROOT / "seed_data"
APP_ENV_VALUES = {"DEV", "STAGING", "PROD"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _reg_set(session: Session, seed_name: str, checksum: str, app_env: str, row_count: int) -> None:
    row = session.exec(select(SeedRegistry).where(SeedRegistry.seed_name == seed_name)).first()
    now = datetime.now(timezone.utc)
    if row:
        row.seed_version = 1
        row.checksum = checksum
        row.environment = app_env
        row.row_count = row_count
        row.applied_at = now
        session.add(row)
    else:
        session.add(
            SeedRegistry(
                seed_name=seed_name,
                seed_version=1,
                checksum=checksum,
                environment=app_env,
                row_count=row_count,
                applied_at=now,
            )
        )
    session.commit()


def _reg_same(session: Session, seed_name: str, checksum: str) -> bool:
    row = session.exec(select(SeedRegistry).where(SeedRegistry.seed_name == seed_name)).first()
    return bool(row and row.seed_version == 1 and row.checksum == checksum)


def _res(c: int = 0, u: int = 0, s: int = 0) -> Dict[str, int]:
    return {"created_count": c, "updated_count": u, "skipped_count": s}


def _terms_inventory_markdown() -> str:
    candidates = [
        ROOT.parent / "terms_of_service.md",
        ROOT / "terms_of_service.md",
        Path.cwd() / "terms_of_service.md",
    ]
    for path in candidates:
        if path.exists():
            txt = path.read_text(encoding="utf-8").strip()
            if txt:
                return txt
    return "# Terms of Service\n\nTerms content is currently unavailable."


def _seed_legal_documents(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    terms_md = _terms_inventory_markdown()
    privacy_md = build_privacy_policy_markdown()
    payload = [
        {"key": "terms_of_service", "version": "seed-v1", "content_md": terms_md},
        {"key": "privacy_policy", "version": "seed-v1", "content_md": privacy_md},
    ]
    checksum = _sha256_payload(payload)
    if _reg_same(session, "legal_documents", checksum):
        count = len(
            session.exec(
                select(LegalDocument).where(LegalDocument.key.in_(["terms_of_service", "privacy_policy"]))
            ).all()
        )
        return count, _res(s=len(payload))

    now = datetime.now(timezone.utc)
    c = u = s = 0
    for row in payload:
        key = row["key"]
        version = row["version"]
        md = row["content_md"]
        html = markdown_to_basic_html(md)
        sha = hashlib.sha256(md.encode("utf-8")).hexdigest()
        existing = session.exec(
            select(LegalDocument).where(LegalDocument.key == key).where(LegalDocument.version == version)
        ).first()
        if existing:
            if (
                existing.status == "published"
                and existing.content_md == md
                and existing.content_html == html
                and existing.checksum_sha256 == sha
            ):
                s += 1
                continue
            existing.status = "published"
            existing.content_md = md
            existing.content_html = html
            existing.effective_at = now
            existing.published_at = now
            existing.checksum_sha256 = sha
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            u += 1
            continue

        session.add(
            LegalDocument(
                key=key,
                version=version,
                status="published",
                content_md=md,
                content_html=html,
                effective_at=now,
                published_at=now,
                checksum_sha256=sha,
            )
        )
        c += 1
    session.commit()
    count = len(
        session.exec(select(LegalDocument).where(LegalDocument.key.in_(["terms_of_service", "privacy_policy"]))).all()
    )
    _reg_set(session, "legal_documents", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_systemconfig(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    payload = _load_json(SEED_DATA_DIR / "systemconfig.json")
    checksum = _sha256_payload(payload)
    if _reg_same(session, "systemconfig", checksum):
        return len(session.exec(select(SystemConfig)).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        cur = session.get(SystemConfig, row["key"])
        if cur:
            if cur.value == str(row["value"]) and cur.description == row.get("description"):
                s += 1
            else:
                cur.value = str(row["value"])
                cur.description = row.get("description")
                cur.updated_at = datetime.utcnow()
                session.add(cur)
                u += 1
        else:
            session.add(SystemConfig(key=row["key"], value=str(row["value"]), description=row.get("description")))
            c += 1
    session.commit()
    count = len(session.exec(select(SystemConfig)).all())
    _reg_set(session, "systemconfig", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_json_schemas(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    path = SEED_DATA_DIR / "json_schemas.json"
    payload = _load_json(path) if path.exists() else []
    checksum = _sha256_payload(payload)
    if _reg_same(session, "json_schemas", checksum):
        return len(session.exec(select(JsonSchemaEntry)).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        cur = session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == row["schema_id"])
            .where(JsonSchemaEntry.version == int(row["version"]))
        ).first()
        if cur:
            if cur.content == row.get("content") and cur.is_active == bool(row.get("is_active", True)):
                s += 1
            else:
                cur.content = row.get("content") or {}
                cur.is_active = bool(row.get("is_active", True))
                cur.updated_by = row.get("updated_by")
                cur.updated_at = datetime.utcnow()
                session.add(cur)
                u += 1
        else:
            session.add(
                JsonSchemaEntry(
                    id=row.get("id") or None,
                    schema_id=row["schema_id"],
                    content=row.get("content") or {},
                    version=int(row["version"]),
                    is_active=bool(row.get("is_active", True)),
                    updated_by=row.get("updated_by"),
                )
            )
            c += 1
    session.commit()
    count = len(session.exec(select(JsonSchemaEntry)).all())
    _reg_set(session, "json_schemas", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_prompt_templates(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    path = SEED_DATA_DIR / "prompt_templates.json"
    if path.exists():
        payload = _load_json(path)
    else:
        payload = []
        legacy_dir = SEED_DATA_DIR / "prompt_templates"
        for file in sorted(legacy_dir.glob("*.json")):
            for row in _load_json(file):
                item = dict(row)
                item.setdefault("version", 1)
                item.setdefault("is_active", True)
                payload.append(item)
    checksum = _sha256_payload(payload)
    if _reg_same(session, "prompt_templates", checksum):
        return len(session.exec(select(PromptTemplateEntry)).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        tier = PromptTierEnum(row["tier"]) if row.get("tier") else None
        cur = session.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.prompt_id == row["prompt_id"])
            .where(PromptTemplateEntry.version == int(row["version"]))
        ).first()
        if cur:
            if (
                cur.tier == tier
                and cur.mode == PromptModeEnum(row["mode"])
                and cur.role == PromptRoleEnum(row["role"])
                and cur.content == row["content"]
                and cur.is_active == bool(row.get("is_active", True))
            ):
                s += 1
            else:
                cur.tier = tier
                cur.mode = PromptModeEnum(row["mode"])
                cur.role = PromptRoleEnum(row["role"])
                cur.content = row["content"]
                cur.is_active = bool(row.get("is_active", True))
                cur.updated_by = row.get("updated_by")
                cur.updated_at = datetime.utcnow()
                session.add(cur)
                u += 1
        else:
            session.add(
                PromptTemplateEntry(
                    id=row.get("id") or None,
                    prompt_id=row["prompt_id"],
                    tier=tier,
                    mode=PromptModeEnum(row["mode"]),
                    role=PromptRoleEnum(row["role"]),
                    content=row["content"],
                    version=int(row["version"]),
                    is_active=bool(row.get("is_active", True)),
                    updated_by=row.get("updated_by") or f"seed:{app_env.lower()}",
                )
            )
            c += 1
    session.commit()
    count = len(session.exec(select(PromptTemplateEntry)).all())
    _reg_set(session, "prompt_templates", checksum, app_env, count)
    return count, _res(c, u, s)


def _validate_binding_refs(session: Session, payload: List[Dict[str, Any]]) -> None:
    prompt_ids = set(session.exec(select(PromptTemplateEntry.prompt_id).distinct()).all())
    schema_ids = set(session.exec(select(JsonSchemaEntry.schema_id).distinct()).all())
    missing_prompts = set()
    missing_schemas = set()
    for row in payload:
        if row["global_system_prompt_id"] not in prompt_ids:
            missing_prompts.add(row["global_system_prompt_id"])
        if row["developer_prompt_id"] not in prompt_ids:
            missing_prompts.add(row["developer_prompt_id"])
        if row["output_schema_id"] not in schema_ids:
            missing_schemas.add(row["output_schema_id"])
    if missing_schemas:
        for schema_id in sorted(missing_schemas):
            content: Dict[str, Any]
            if schema_id == "na_math_solver_v3":
                from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3

                content = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "na_math_solver_v3",
                        "strict": True,
                        "schema": get_json_schema_for_openai_v3(),
                    },
                }
            else:
                content = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_id,
                        "strict": True,
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                }
            session.add(
                JsonSchemaEntry(
                    schema_id=schema_id,
                    content=content,
                    version=1,
                    is_active=True,
                    updated_by="seed:bootstrap",
                )
            )
        session.commit()
        schema_ids = set(session.exec(select(JsonSchemaEntry.schema_id).distinct()).all())
        missing_schemas = {row["output_schema_id"] for row in payload if row["output_schema_id"] not in schema_ids}
    if missing_prompts or missing_schemas:
        raise RuntimeError(
            "Prompt binding reference validation failed: "
            f"missing_prompts={sorted(missing_prompts)} missing_schemas={sorted(missing_schemas)}"
        )


def _sync_prompt_schema_key_tables(session: Session) -> None:
    # Key tables are created by migration f7a9c2d41e11; keep them aligned before binding upserts.
    try:
        session.exec(
            text(
                """
                INSERT INTO prompt_template_keys(prompt_id)
                SELECT DISTINCT prompt_id FROM prompt_templates
                ON CONFLICT (prompt_id) DO NOTHING
                """
            )
        )
        session.exec(
            text(
                """
                INSERT INTO json_schema_keys(schema_id)
                SELECT DISTINCT schema_id FROM json_schemas
                ON CONFLICT (schema_id) DO NOTHING
                """
            )
        )
        session.commit()
    except Exception:
        session.rollback()


def _seed_prompt_bindings(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    payload = _load_json(SEED_DATA_DIR / "prompt_bindings.json")
    _validate_binding_refs(session, payload)
    checksum = _sha256_payload(payload)
    if _reg_same(session, "prompt_bindings", checksum):
        return len(session.exec(select(PromptBinding)).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        tier = PromptTierEnum(row["tier"])
        mode = PromptModeEnum(row["mode"])
        trim = TrimStrategyEnum(row["trim_strategy"]) if row.get("trim_strategy") else None
        cur = None
        if row.get("id"):
            cur = session.exec(select(PromptBinding).where(PromptBinding.id == row["id"])).first()
        if not cur:
            cur = session.exec(
                select(PromptBinding)
                .where(PromptBinding.tier == tier)
                .where(PromptBinding.mode == mode)
                .where(PromptBinding.global_system_prompt_id == row["global_system_prompt_id"])
                .where(PromptBinding.developer_prompt_id == row["developer_prompt_id"])
                .where(PromptBinding.output_schema_id == row["output_schema_id"])
            ).first()
        if cur:
            fields = {
                "tier": tier,
                "mode": mode,
                "global_system_prompt_id": row["global_system_prompt_id"],
                "developer_prompt_id": row["developer_prompt_id"],
                "output_schema_id": row["output_schema_id"],
                "max_output_tokens": row.get("max_output_tokens"),
                "max_input_tokens": row.get("max_input_tokens"),
                "max_questions_allowed": row.get("max_questions_allowed"),
                "system_schema_budget_tokens": row.get("system_schema_budget_tokens"),
                "context_budget_tokens": row.get("context_budget_tokens"),
                "json_retry_max_output_tokens": row.get("json_retry_max_output_tokens"),
                "json_retry_max_attempts": row.get("json_retry_max_attempts"),
                "timeout_ms": row.get("timeout_ms"),
                "temperature": row.get("temperature"),
                "top_p": row.get("top_p"),
                "plot_points_cap": row.get("plot_points_cap"),
                "plot_traces_cap": row.get("plot_traces_cap"),
                "plot_annotations_cap": row.get("plot_annotations_cap"),
                "trim_strategy": trim,
                "max_steps": row.get("max_steps"),
                "retry_cap_tokens": row.get("retry_cap_tokens"),
                "features": row.get("features") or {},
                "multipliers": row.get("multipliers") or {},
                "is_active": bool(row.get("is_active", True)),
            }
            changed = False
            for k, v in fields.items():
                if getattr(cur, k) != v:
                    setattr(cur, k, v)
                    changed = True
            if changed:
                cur.updated_by = row.get("updated_by") or f"seed:{app_env.lower()}"
                cur.updated_at = datetime.utcnow()
                session.add(cur)
                u += 1
            else:
                s += 1
        else:
            session.add(
                PromptBinding(
                    id=row.get("id") or None,
                    tier=tier,
                    mode=mode,
                    global_system_prompt_id=row["global_system_prompt_id"],
                    developer_prompt_id=row["developer_prompt_id"],
                    output_schema_id=row["output_schema_id"],
                    max_output_tokens=row.get("max_output_tokens"),
                    max_input_tokens=row.get("max_input_tokens"),
                    max_questions_allowed=row.get("max_questions_allowed"),
                    system_schema_budget_tokens=row.get("system_schema_budget_tokens"),
                    context_budget_tokens=row.get("context_budget_tokens"),
                    json_retry_max_output_tokens=row.get("json_retry_max_output_tokens"),
                    json_retry_max_attempts=row.get("json_retry_max_attempts"),
                    timeout_ms=row.get("timeout_ms"),
                    temperature=row.get("temperature"),
                    top_p=row.get("top_p"),
                    plot_points_cap=row.get("plot_points_cap"),
                    plot_traces_cap=row.get("plot_traces_cap"),
                    plot_annotations_cap=row.get("plot_annotations_cap"),
                    trim_strategy=trim,
                    max_steps=row.get("max_steps"),
                    retry_cap_tokens=row.get("retry_cap_tokens"),
                    features=row.get("features") or {},
                    multipliers=row.get("multipliers") or {},
                    is_active=bool(row.get("is_active", True)),
                    updated_by=row.get("updated_by") or f"seed:{app_env.lower()}",
                )
            )
            c += 1
    session.commit()
    count = len(session.exec(select(PromptBinding)).all())
    _reg_set(session, "prompt_bindings", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_provider_pricing(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    payload = _load_json(SEED_DATA_DIR / "providermodelpricing.json")
    checksum = _sha256_payload(payload)
    if _reg_same(session, "providermodelpricing", checksum):
        return len(session.exec(select(ProviderModelPricing)).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        cur = session.exec(
            select(ProviderModelPricing)
            .where(ProviderModelPricing.provider == row["provider"])
            .where(ProviderModelPricing.model == row["model"])
            .where(ProviderModelPricing.status == row.get("status", "ACTIVE"))
        ).first()
        if cur:
            if (
                cur.price_in_per_1m == float(row["price_in_per_1m"])
                and cur.price_out_per_1m == float(row["price_out_per_1m"])
                and cur.price_cached_in_per_1m == float(row.get("price_cached_in_per_1m") or 0.0)
            ):
                s += 1
            else:
                cur.price_in_per_1m = float(row["price_in_per_1m"])
                cur.price_out_per_1m = float(row["price_out_per_1m"])
                cur.price_cached_in_per_1m = float(row.get("price_cached_in_per_1m") or 0.0)
                cur.currency = row.get("currency", "USD")
                cur.change_reason = row.get("change_reason")
                session.add(cur)
                u += 1
        else:
            session.add(
                ProviderModelPricing(
                    provider=row["provider"],
                    model=row["model"],
                    price_in_per_1m=float(row["price_in_per_1m"]),
                    price_out_per_1m=float(row["price_out_per_1m"]),
                    price_cached_in_per_1m=float(row.get("price_cached_in_per_1m") or 0.0),
                    currency=row.get("currency", "USD"),
                    status=row.get("status", "ACTIVE"),
                    change_reason=row.get("change_reason"),
                )
            )
            c += 1
    session.commit()
    count = len(session.exec(select(ProviderModelPricing)).all())
    _reg_set(session, "providermodelpricing", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_programs_and_plans(session: Session, app_env: str) -> Tuple[int, int, Dict[str, Dict[str, int]]]:
    payload = _load_json(SEED_DATA_DIR / "credit_programs_or_plans.json")
    checksum = _sha256_payload(payload)
    if _reg_same(session, "credit_programs_or_plans", checksum):
        p_count = len(session.exec(select(CreditProgramDefinition)).all())
        pl_count = len(session.exec(select(Plan)).all())
        return p_count, pl_count, {
            "p_ops": _res(s=len(payload.get("credit_programs", []))),
            "pl_ops": _res(s=len(payload.get("plans", [])))
        }

    pc = pu = ps = 0
    plc = plu = pls = 0

    for row in payload.get("credit_programs", []):
        cur = session.exec(select(CreditProgramDefinition).where(CreditProgramDefinition.slug == row["slug"])).first()
        if cur:
            if cur.name == row["name"] and cur.status == row.get("status", "active"):
                ps += 1
            else:
                cur.name = row["name"]
                cur.description = row.get("description")
                cur.status = row.get("status", "active")
                cur.monthly_gift_credits = Decimal(str(row.get("monthly_gift_credits", 0)))
                cur.gift_expiry_window_days = int(row.get("gift_expiry_window_days", 30))
                cur.entitlements = row.get("entitlements")
                cur.updated_at = datetime.utcnow()
                session.add(cur)
                pu += 1
        else:
            session.add(
                CreditProgramDefinition(
                    name=row["name"],
                    slug=row["slug"],
                    description=row.get("description"),
                    status=row.get("status", "active"),
                    monthly_gift_credits=Decimal(str(row.get("monthly_gift_credits", 0))),
                    gift_expiry_window_days=int(row.get("gift_expiry_window_days", 30)),
                    entitlements=row.get("entitlements"),
                )
            )
            pc += 1

    for row in payload.get("plans", []):
        cur = session.exec(select(Plan).where(Plan.slug == row["slug"])).first()
        if cur:
            if cur.name == row["name"] and cur.credits_per_month == int(row["credits_per_month"]):
                pls += 1
            else:
                cur.name = row["name"]
                cur.credits_per_month = int(row["credits_per_month"])
                cur.price_monthly_cents = int(row["price_monthly_cents"])
                cur.price_yearly_cents = int(row["price_yearly_cents"])
                cur.seats = int(row.get("seats", 1))
                cur.features = row.get("features") or {}
                cur.multipliers = row.get("multipliers") or {}
                cur.is_active = True
                session.add(cur)
                plu += 1
        else:
            session.add(
                Plan(
                    name=row["name"],
                    slug=row["slug"],
                    credits_per_month=int(row["credits_per_month"]),
                    price_monthly_cents=int(row["price_monthly_cents"]),
                    price_yearly_cents=int(row["price_yearly_cents"]),
                    seats=int(row.get("seats", 1)),
                    features=row.get("features") or {},
                    multipliers=row.get("multipliers") or {},
                    is_active=True,
                )
            )
            plc += 1
    session.commit()
    p_count = len(session.exec(select(CreditProgramDefinition)).all())
    pl_count = len(session.exec(select(Plan)).all())
    _reg_set(session, "credit_programs_or_plans", checksum, app_env, p_count + pl_count)
    return p_count, pl_count, {"p_ops": _res(pc, pu, ps), "pl_ops": _res(plc, plu, pls)}


def _seed_topup_products(session: Session) -> Tuple[int, Dict[str, int]]:
    existing = session.exec(select(TopUpProduct)).all()
    if existing:
        return len(existing), _res(s=len(existing))

    defaults = [
        ("topup_5", "$5 Pack", 550, 5.0),
        ("topup_10", "$10 Pack", 1200, 10.0),
        ("topup_25", "$25 Pack", 3250, 25.0),
        ("topup_50", "$50 Pack", 7000, 50.0),
    ]
    created = 0
    for code, name, credits, price in defaults:
        session.add(
            TopUpProduct(
                code=code,
                name=name,
                credits=credits,
                price_usd=price,
                is_active=True,
            )
        )
        created += 1
    session.commit()
    return created, _res(c=created)


def _seed_schools(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    ca_csv = ROOT / "data" / "schools_ca.csv"
    us_csv = ROOT / "data" / "schools_us.csv"
    payload = {
        "ca_csv": str(ca_csv),
        "us_csv": str(us_csv),
        "ca_mtime": ca_csv.stat().st_mtime if ca_csv.exists() else 0,
        "us_mtime": us_csv.stat().st_mtime if us_csv.exists() else 0,
    }
    checksum = _sha256_payload(payload)
    if _reg_same(session, "school", checksum):
        return len(session.exec(select(School)).all()), _res(s=1)
    if not ca_csv.exists() or not us_csv.exists():
        raise RuntimeError(f"School CSV not found: {ca_csv} or {us_csv}")
    before = len(session.exec(select(School)).all())
    import_school_csvs(session=session, canada_csv_path=ca_csv, us_csv_path=us_csv)
    after = len(session.exec(select(School)).all())
    _reg_set(session, "school", checksum, app_env, after)
    if after > before:
        return after, _res(c=after - before)
    return after, _res(u=1)


def _seed_internal_users(session: Session, app_env: str, allow_user_seeding: bool, dev_fixtures: bool) -> Tuple[int, Dict[str, int]]:
    if not allow_user_seeding:
        return len(session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all()), _res()
    override_path = os.environ.get("SEED_INTERNAL_USERS_JSON")
    if override_path:
        path = Path(override_path).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise RuntimeError(f"SEED_INTERNAL_USERS_JSON not found: {path}")
        payload = _load_json(path)
    else:
        path = SEED_DATA_DIR / "internal_users.json"
        payload = _load_json(path) if path.exists() else _load_json(SEED_DATA_DIR / "internal_users.example.json")

    if not override_path:
        superadmin_emails = {
            os.environ.get("SEED_PRIMARY_SUPERADMIN_EMAIL", "admin@uask.ai").strip().lower(),
            os.environ.get("SEED_SECOND_SUPERADMIN_EMAIL", "loai@uask.ai").strip().lower(),
        }
        superadmin_emails = {x for x in superadmin_emails if x}
        if app_env == "DEV":
            for email in sorted(superadmin_emails):
                existing = next((r for r in payload if r.get("email", "").strip().lower() == email), None)
                if existing is None:
                    payload.insert(
                        0,
                        {
                            "email": email,
                            "full_name": email.split("@")[0],
                            "role": "superadmin",
                            "is_verified": True,
                        },
                    )
            for row in payload:
                email = row.get("email", "").strip().lower()
                if email in superadmin_emails:
                    row["role"] = "superadmin"
                elif row.get("role") == "superadmin":
                    row["role"] = "admin"
        else:
            for row in payload:
                email = row.get("email", "").strip().lower()
                if email in superadmin_emails:
                    row["role"] = "superadmin"
    default_password = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "admin1234")
    checksum_payload = []
    for row in payload:
        password_env = row.get("password_env")
        resolved = os.environ.get(password_env, default_password) if password_env else default_password
        password_fingerprint = hashlib.sha256(resolved.encode("utf-8")).hexdigest()
        checksum_payload.append(
            {
                "email": row.get("email"),
                "full_name": row.get("full_name"),
                "role": row.get("role"),
                "subscription_tier": row.get("subscription_tier", "standard"),
                "password_env": password_env,
                "password_fingerprint": password_fingerprint,
            }
        )
    checksum = _sha256_payload(checksum_payload)
    if _reg_same(session, "internal_users", checksum):
        return len(session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all()), _res(s=len(payload))
    c = u = s = 0
    for row in payload:
        email = row["email"].strip().lower()
        cur = session.exec(select(User).where(User.email == email)).first()
        password_env = row.get("password_env")
        plain = os.environ.get(password_env, default_password) if password_env else default_password
        password_hash = get_password_hash(plain)
        force_password_update = True

        if cur:
            changed = False
            for key, val in [
                ("full_name", row.get("full_name", email.split("@")[0])),
                ("role", row.get("role", "employee")),
                ("is_internal", True),
                ("is_verified", bool(row.get("is_verified", True))),
                ("subscription_tier", row.get("subscription_tier", "standard")),
            ]:
                if getattr(cur, key) != val:
                    setattr(cur, key, val)
                    changed = True
            if password_hash and (force_password_update or cur.password_hash != password_hash):
                cur.password_hash = password_hash
                changed = True
            if changed:
                session.add(cur)
                u += 1
            else:
                s += 1
        else:
            if not password_hash:
                plain = os.environ.get(row.get("password_env", ""), default_password)
                password_hash = get_password_hash(plain)
            session.add(
                User(
                    email=email,
                    full_name=row.get("full_name", email.split("@")[0]),
                    role=row.get("role", "employee"),
                    is_internal=True,
                    is_verified=bool(row.get("is_verified", True)),
                    password_hash=password_hash,
                    subscription_tier=row.get("subscription_tier", "standard"),
                )
            )
            c += 1
    session.commit()
    if app_env == "DEV" and dev_fixtures:
        users = session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all()
        for user in users:
            lot = session.exec(
                select(CreditLot)
                .where(CreditLot.user_id == user.id)
                .where(CreditLot.source == "DEV_FIXTURE")
                .where(CreditLot.reason_code == "DEV_UI")
            ).first()
            if lot:
                continue
            session.add(
                CreditLot(
                    user_id=user.id,
                    credits_total=Decimal("1000"),
                    credits_remaining=Decimal("1000"),
                    lot_type="GRANT",
                    status="ACTIVE",
                    source="DEV_FIXTURE",
                    reason_code="DEV_UI",
                )
            )
        session.commit()
    count = len(session.exec(select(User).where(User.is_internal == True).where(User.email.like("%@uask.ai"))).all())
    _reg_set(session, "internal_users", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_credit_transfers(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    path = SEED_DATA_DIR / "credit_transfers.json"
    payload = _load_json(path) if path.exists() else []
    checksum = _sha256_payload(payload)
    if _reg_same(session, "credit_transfers", checksum):
        return len(session.exec(select(CreditTransfer)).all()), _res(s=len(payload))

    c = u = s = 0
    for row in payload:
        cur = session.get(CreditTransfer, row["id"])
        values = {
            "sender_user_id": int(row["sender_user_id"]),
            "recipient_email": str(row["recipient_email"]).strip().lower(),
            "recipient_user_id": row.get("recipient_user_id"),
            "amount": Decimal(str(row["amount"])),
            "status": row.get("status", "PENDING"),
            "idempotency_key": row["idempotency_key"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
            "expires_at": datetime.fromisoformat(row["expires_at"]),
            "claimed_at": datetime.fromisoformat(row["claimed_at"]) if row.get("claimed_at") else None,
            "failure_reason": row.get("failure_reason"),
            "sender_ip_hash": row.get("sender_ip_hash"),
            "escrow_lot_id": row.get("escrow_lot_id"),
            "sender_ledger_id": row.get("sender_ledger_id"),
            "recipient_ledger_id": row.get("recipient_ledger_id"),
            "refund_ledger_id": row.get("refund_ledger_id"),
        }
        if cur:
            changed = False
            for k, v in values.items():
                if getattr(cur, k) != v:
                    setattr(cur, k, v)
                    changed = True
            if changed:
                session.add(cur)
                u += 1
            else:
                s += 1
        else:
            session.add(CreditTransfer(id=row["id"], **values))
            c += 1
    session.commit()
    count = len(session.exec(select(CreditTransfer)).all())
    _reg_set(session, "credit_transfers", checksum, app_env, count)
    return count, _res(c, u, s)


def _seed_notifications(session: Session, app_env: str) -> Tuple[int, Dict[str, int]]:
    path = SEED_DATA_DIR / "notifications.json"
    payload = _load_json(path) if path.exists() else []
    checksum = _sha256_payload(payload)
    if _reg_same(session, "notifications", checksum):
        return len(session.exec(select(Notification)).all()), _res(s=len(payload))

    c = u = s = 0
    for row in payload:
        cur = session.get(Notification, int(row["id"]))
        values = {
            "user_id": int(row["user_id"]),
            "type": row["type"],
            "title": row["title"],
            "body": row["body"],
            "payload_json": row.get("payload_json"),
            "severity": row.get("severity", "info"),
            "is_read": bool(row.get("is_read", False)),
            "created_at": datetime.fromisoformat(row["created_at"]),
            "read_at": datetime.fromisoformat(row["read_at"]) if row.get("read_at") else None,
            "action_type": row.get("action_type"),
            "action_payload": row.get("action_payload"),
            "dedupe_key": row.get("dedupe_key"),
        }
        if cur:
            changed = False
            for k, v in values.items():
                if getattr(cur, k) != v:
                    setattr(cur, k, v)
                    changed = True
            if changed:
                session.add(cur)
                u += 1
            else:
                s += 1
        else:
            session.add(Notification(id=int(row["id"]), **values))
            c += 1
    session.commit()
    count = len(session.exec(select(Notification)).all())
    _reg_set(session, "notifications", checksum, app_env, count)
    return count, _res(c, u, s)


def _assert_no_payment_transactions(session: Session) -> None:
    row_count = len(session.exec(select(Payment)).all())
    if row_count > 0:
        app_env = (os.getenv("APP_ENV") or "DEV").upper()
        if app_env in {"DEV", "TEST"}:
            # Dev/test safety: remove any payment artifacts so seeding can proceed.
            session.exec(sa.text("TRUNCATE TABLE payment RESTART IDENTITY CASCADE"))
            session.commit()
            return
        raise RuntimeError(f"Payment table is not empty ({row_count} rows). Seeder must never seed payment transactions.")


def run_seed(app_env: str, rotate_passwords: bool, dev_fixtures: bool, allow_user_seeding: bool = True) -> Dict[str, Dict[str, int]]:
    if app_env not in APP_ENV_VALUES:
        raise RuntimeError(f"Unsupported env {app_env}. Expected one of {sorted(APP_ENV_VALUES)}")
    if app_env in {"STAGING", "PROD"} and dev_fixtures:
        raise RuntimeError("--dev-fixtures is DEV-only.")
    summary: Dict[str, Dict[str, int]] = {}
    with Session(engine) as session:
        count, ops = _seed_systemconfig(session, app_env)
        summary["systemconfig"] = {"row_count": count, **ops}
        count, ops = _seed_json_schemas(session, app_env)
        summary["json_schemas"] = {"row_count": count, **ops}
        count, ops = _seed_prompt_templates(session, app_env)
        summary["prompt_templates"] = {"row_count": count, **ops}
        summary["prompt_schema_links"] = {"row_count": 0, **_res()}
        _sync_prompt_schema_key_tables(session)
        count, ops = _seed_prompt_bindings(session, app_env)
        summary["prompt_bindings"] = {"row_count": count, **ops}
        count, ops = _seed_provider_pricing(session, app_env)
        summary["providermodelpricing"] = {"row_count": count, **ops}
        p_count, pl_count, ops_map = _seed_programs_and_plans(session, app_env)
        summary["creditprogramdefinition"] = {"row_count": p_count, **ops_map["p_ops"]}
        summary["plan"] = {"row_count": pl_count, **ops_map["pl_ops"]}
        pack_count, pack_ops = _seed_topup_products(session)
        summary["topup_product"] = {"row_count": pack_count, **pack_ops}
        count, ops = _seed_schools(session, app_env)
        summary["school"] = {"row_count": count, **ops}
        count, ops = _seed_internal_users(session, app_env, allow_user_seeding, dev_fixtures)
        summary["user"] = {"row_count": count, **ops}
        count, ops = _seed_credit_transfers(session, app_env)
        summary["credit_transfers"] = {"row_count": count, **ops}
        count, ops = _seed_notifications(session, app_env)
        summary["notifications"] = {"row_count": count, **ops}
        count, ops = _seed_legal_documents(session, app_env)
        summary["legal_documents"] = {"row_count": count, **ops}
        _assert_no_payment_transactions(session)
        summary["payment"] = {"row_count": 0, **_res()}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Environment-aware production seeder.")
    parser.add_argument("--env", required=True, choices=sorted(APP_ENV_VALUES))
    parser.add_argument("--rotate-passwords", action="store_true", help="Compatibility flag.")
    parser.add_argument("--dev-fixtures", action="store_true", help="Create DEV-only fixture lots.")
    parser.add_argument("--disallow-user-seeding", action="store_true", help="Do not create/update internal users.")
    args = parser.parse_args()
    summary = run_seed(args.env, args.rotate_passwords, args.dev_fixtures, allow_user_seeding=not args.disallow_user_seeding)
    print("Seed completed:")
    for k in [
        "systemconfig",
        "json_schemas",
        "prompt_templates",
        "prompt_schema_links",
        "prompt_bindings",
        "providermodelpricing",
        "creditprogramdefinition",
        "plan",
        "topup_product",
        "school",
        "user",
        "credit_transfers",
        "notifications",
        "legal_documents",
        "payment",
    ]:
        row = summary.get(k, {})
        print(
            f"  {k}: row_count={row.get('row_count', 0)} "
            f"created={row.get('created_count', 0)} "
            f"updated={row.get('updated_count', 0)} "
            f"skipped={row.get('skipped_count', 0)}"
        )


if __name__ == "__main__":
    main()
