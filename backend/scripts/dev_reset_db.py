import argparse
import os
from typing import Dict, List, Tuple

from sqlalchemy import inspect, text
from sqlmodel import Session

from app.database import engine


PRESERVE_TABLES_SAFE = {
    "alembic_version",
    "seed_registry",
    "school",
    "prompt_templates",
    "prompt_bindings",
    "providermodelpricing",
    "systemconfig",
    "plan",
    "creditprogramdefinition",
    "payment",
    "user",
}


def _assert_dev_or_override() -> None:
    app_env = os.environ.get("APP_ENV", "").upper()
    allow_override = os.environ.get("ALLOW_DESTRUCTIVE_DEV_RESET", "").lower() in {"1", "true", "yes"}
    if app_env == "DEV" or allow_override:
        return
    raise RuntimeError(
        "Refusing reset outside DEV. Set APP_ENV=DEV or ALLOW_DESTRUCTIVE_DEV_RESET=true (explicit override)."
    )


def _quoted(name: str) -> str:
    return f'"{name}"'


def _all_public_tables() -> List[str]:
    inspector = inspect(engine)
    return sorted(inspector.get_table_names(schema="public"))


def _row_count(session: Session, table_name: str) -> int:
    return int(session.exec(text(f"SELECT COUNT(*) FROM public.{_quoted(table_name)}")).one())


def _truncate_tables(session: Session, tables: List[str]) -> None:
    if not tables:
        return
    joined = ", ".join(f"public.{_quoted(t)}" for t in tables)
    session.exec(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
    session.commit()


def _collect_counts(session: Session, tables: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for table in tables:
        out[table] = _row_count(session, table)
    return out


def reset_dev_db(mode: str) -> Tuple[Dict[str, int], Dict[str, int], List[str]]:
    _assert_dev_or_override()
    all_tables = _all_public_tables()
    with Session(engine) as session:
        if mode == "NUKE":
            target_tables = [t for t in all_tables if t != "alembic_version"]
        else:
            target_tables = [t for t in all_tables if t not in PRESERVE_TABLES_SAFE]

        before = _collect_counts(session, target_tables)
        _truncate_tables(session, target_tables)
        after = _collect_counts(session, target_tables)
        return before, after, target_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV-only reset utility.")
    parser.add_argument("--mode", required=True, choices=["NUKE", "SAFE"])
    parser.add_argument("--confirm", required=True, help='Must equal "RESET_DEV_DB"')
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()

    if args.confirm != "RESET_DEV_DB":
        raise RuntimeError('Confirmation failed. Pass --confirm "RESET_DEV_DB"')

    before, after, tables = reset_dev_db(args.mode)
    print(f"Reset mode={args.mode}")
    print("Tables cleared:")
    for table in tables:
        print(f"  {table}: before={before.get(table, 0)} after={after.get(table, 0)}")


if __name__ == "__main__":
    main()
