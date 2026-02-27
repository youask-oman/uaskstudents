import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

from app.database import engine


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "seed_data_fresh"


# Primary runtime tables for the current product surface.
PRIMARY_TABLES: List[str] = [
    "user",
    "school",
    "systemconfig",
    "json_schemas",
    "prompt_templates",
    "prompt_bindings",
    "providermodelpricing",
    "creditprogramdefinition",
    "plan",
    "topupproduct",
    "legal_documents",
    "credit_transfers",
    "notifications",
    "chatsession",
    "chatmessage",
    "solvesession",
    "solveroutputattempt",
    "upload",
    "payment",
    "subscription",
]


# Essential seed tables for environment bootstrap.
ESSENTIAL_SEED_TABLES: List[str] = [
    "user",
    "systemconfig",
    "json_schemas",
    "prompt_templates",
    "prompt_bindings",
    "providermodelpricing",
    "creditprogramdefinition",
    "plan",
    "topupproduct",
    "legal_documents",
    "credit_transfers",
    "notifications",
]


DEFAULT_ORDER_BY: Dict[str, List[str]] = {
    "user": ["id"],
    "systemconfig": ["key"],
    "json_schemas": ["schema_id", "version", "id"],
    "prompt_templates": ["prompt_id", "version", "id"],
    "prompt_bindings": ["tier", "mode", "id"],
    "providermodelpricing": ["provider", "model", "effective_from", "id"],
    "creditprogramdefinition": ["slug", "id"],
    "plan": ["slug", "id"],
    "topupproduct": ["code", "id"],
    "legal_documents": ["key", "version", "id"],
    "credit_transfers": ["id"],
    "notifications": ["id"],
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    path.write_text(text_payload, encoding="utf-8")


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.tables
            where table_schema = 'public' and table_name = :table_name
            limit 1
            """
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _list_columns(conn, table_name: str) -> List[str]:
    rows = conn.execute(
        text(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = :table_name
            order by ordinal_position
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return [str(r[0]) for r in rows]


def _export_table(conn, table_name: str) -> Dict[str, Any]:
    columns = _list_columns(conn, table_name)
    if not columns:
        return {"table": table_name, "row_count": 0, "sha256": _sha256([]), "file": f"{table_name}.json"}

    order_columns = [c for c in DEFAULT_ORDER_BY.get(table_name, []) if c in columns]
    order_clause = ""
    if order_columns:
        quoted = ", ".join(f'"{col}"' for col in order_columns)
        order_clause = f" order by {quoted}"

    query = text(f'select * from "{table_name}"{order_clause}')
    rows = conn.execute(query).mappings().all()
    payload = [{k: _jsonable(v) for k, v in dict(row).items()} for row in rows]
    out_name = f"{table_name}.json"
    return {
        "table": table_name,
        "row_count": len(payload),
        "sha256": _sha256(payload),
        "file": out_name,
        "payload": payload,
    }


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return sum(1 for _ in reader)


def export_fresh_seed_bundle(out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    files: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                select tablename
                from pg_tables
                where schemaname='public'
                order by tablename
                """
            )
        ).fetchall()
        db_tables = [str(r[0]) for r in rows]

        for table in ESSENTIAL_SEED_TABLES:
            if not _table_exists(conn, table):
                warnings.append(f"missing_table:{table}")
                continue
            exported = _export_table(conn, table)
            payload = exported.pop("payload")
            _write_json(out_dir / exported["file"], payload)
            files[exported["file"]] = exported

    ca_csv = ROOT / "data" / "schools_ca.csv"
    us_csv = ROOT / "data" / "schools_us.csv"
    school_source = {
        "source": "csv_only",
        "files": {
            "schools_ca.csv": {
                "path": str(ca_csv),
                "exists": ca_csv.exists(),
                "row_count": _count_csv_rows(ca_csv),
                "sha256": hashlib.sha256(ca_csv.read_bytes()).hexdigest() if ca_csv.exists() else None,
            },
            "schools_us.csv": {
                "path": str(us_csv),
                "exists": us_csv.exists(),
                "row_count": _count_csv_rows(us_csv),
                "sha256": hashlib.sha256(us_csv.read_bytes()).hexdigest() if us_csv.exists() else None,
            },
        },
    }
    _write_json(out_dir / "school.seed_source.json", school_source)
    files["school.seed_source.json"] = {
        "table": "school",
        "row_count": school_source["files"]["schools_ca.csv"]["row_count"] + school_source["files"]["schools_us.csv"]["row_count"],
        "sha256": _sha256(school_source),
        "file": "school.seed_source.json",
    }

    table_inventory = {
        "primary_tables": PRIMARY_TABLES,
        "essential_seed_tables": ESSENTIAL_SEED_TABLES + ["school(csv)"],
        "db_public_tables": db_tables,
    }
    _write_json(out_dir / "table_inventory.json", table_inventory)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "current_database",
        "note": "Fresh export from live DB. Do not mix with legacy seed files.",
        "files": files,
        "warnings": warnings,
    }
    _write_json(out_dir / "seed_manifest.fresh.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export fresh seed files from the current DB snapshot.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output folder for fresh seed bundle.")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete existing JSON files in output folder before export.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.wipe:
        for path in out_dir.glob("*.json"):
            path.unlink()

    manifest = export_fresh_seed_bundle(out_dir)
    print(f"fresh_seed_bundle={out_dir}")
    for file_name in sorted(manifest["files"].keys()):
        meta = manifest["files"][file_name]
        print(f"{file_name}: rows={meta['row_count']} sha256={meta['sha256']}")


if __name__ == "__main__":
    main()

