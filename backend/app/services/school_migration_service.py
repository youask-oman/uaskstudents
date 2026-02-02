from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import inspect, text

from app.models import School
from app.services.school_import_service import stable_school_key


def _canonical_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip().upper()
    if raw in {"US", "USA", "UNITED STATES"}:
        return "US"
    if raw in {"CA", "CANADA"}:
        return "CA"
    return raw


def _canonical_source(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip().lower()
    if raw in {"us_csv", "nces_csv"}:
        return "nces_csv"
    if raw in {"ca_csv", "canada_csv"}:
        return "canada_csv"
    return raw


def _fetch_old_school_rows(conn) -> List[Dict]:
    result = conn.execute(text("SELECT * FROM school"))
    return [dict(row) for row in result.mappings().all()]


def _backup_school_table(conn, dialect: str) -> None:
    conn.execute(text("DROP TABLE IF EXISTS school_legacy"))
    if dialect == "postgresql":
        conn.execute(text("CREATE TABLE school_legacy AS TABLE school WITH DATA"))
    else:
        conn.execute(text("CREATE TABLE school_legacy AS SELECT * FROM school"))


def _drop_user_school_fk_if_exists(conn, dialect: str) -> None:
    inspector = inspect(conn)
    if not inspector.has_table("user"):
        return

    if dialect == "postgresql":
        constraints = conn.execute(
            text(
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = 'user'
                  AND con.contype = 'f'
                  AND con.confrelid = 'school'::regclass
                """
            )
        ).scalars().all()
        for name in constraints:
            conn.execute(text(f'ALTER TABLE "user" DROP CONSTRAINT IF EXISTS "{name}"'))


def _restore_user_school_fk_if_missing(conn, dialect: str) -> None:
    inspector = inspect(conn)
    if not inspector.has_table("user"):
        return

    if dialect == "postgresql":
        existing = conn.execute(
            text(
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = 'user'
                  AND con.contype = 'f'
                  AND con.confrelid = 'school'::regclass
                """
            )
        ).scalars().all()
        if not existing:
            conn.execute(
                text(
                    'ALTER TABLE "user" ADD CONSTRAINT user_school_id_fkey '
                    "FOREIGN KEY (school_id) REFERENCES school(id) ON DELETE SET NULL"
                )
            )


def _to_new_school_row(old_row: Dict) -> Dict:
    country = _canonical_country(old_row.get("country")) or "US"
    source = _canonical_source(old_row.get("source")) or ("nces_csv" if country == "US" else "canada_csv")
    external_id = str(old_row.get("external_id")).strip() if old_row.get("external_id") is not None else None
    school_key = old_row.get("school_key")
    if not school_key and external_id:
        school_key = stable_school_key(country, source, external_id)

    address_line1 = None
    full_address = None
    city = old_row.get("city")
    province = old_row.get("province_state")
    if city and province:
        full_address = f"{city}, {province}"

    return {
        "id": old_row.get("id"),
        "country": country,
        "province_state": province,
        "district": old_row.get("district"),
        "city": city,
        "school_name": old_row.get("school_name"),
        "school_type": old_row.get("school_type"),
        "grade_range": old_row.get("grade_range"),
        "external_id": external_id,
        "source": source,
        "school_key": school_key,
        "website_url": None,
        "address_line1": address_line1,
        "full_address": full_address,
        "street_no": None,
        "street_name": None,
        "postal_code": None,
        "latitude": None,
        "longitude": None,
        "csdname": None,
        "csduid": None,
        "normalized_name": None,
        "normalized_address": None,
        "created_at": old_row.get("created_at") or datetime.utcnow(),
        "updated_at": old_row.get("updated_at") or datetime.utcnow(),
    }


def migrate_school_table(engine, backfill_old_rows: bool = True, create_trgm_index: bool = True) -> Dict:
    summary = {"backup_rows": 0, "backfilled_rows": 0}
    dialect = engine.dialect.name

    with engine.begin() as conn:
        inspector = inspect(conn)
        has_school = inspector.has_table("school")

        if not has_school:
            School.__table__.create(bind=conn, checkfirst=True)
            if dialect == "postgresql" and create_trgm_index:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_school_normalized_name_trgm "
                        "ON school USING gin (normalized_name gin_trgm_ops)"
                    )
                )
            return summary

        old_rows = _fetch_old_school_rows(conn)
        summary["backup_rows"] = len(old_rows)

        _backup_school_table(conn, dialect)
        _drop_user_school_fk_if_exists(conn, dialect)
        conn.execute(text("DROP TABLE school"))

        School.__table__.create(bind=conn, checkfirst=True)

        if backfill_old_rows and old_rows:
            new_rows = [_to_new_school_row(row) for row in old_rows]
            conn.execute(School.__table__.insert(), new_rows)
            summary["backfilled_rows"] = len(new_rows)

        if dialect == "postgresql":
            conn.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('school','id'), "
                    "COALESCE((SELECT MAX(id) FROM school), 1), true)"
                )
            )
            if create_trgm_index:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_school_normalized_name_trgm "
                        "ON school USING gin (normalized_name gin_trgm_ops)"
                    )
                )

        _restore_user_school_fk_if_missing(conn, dialect)

    return summary
