import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from app.services.school_import_service import import_school_csvs
from app.services.school_migration_service import migrate_school_table


def _create_temp_database_url() -> str:
    import os

    base_url = os.getenv("TEST_POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not base_url:
        pytest.skip("No TEST_POSTGRES_URL or DATABASE_URL configured for integration test.")
    if not base_url.startswith("postgresql"):
        pytest.skip("Integration test requires a PostgreSQL URL.")

    base = make_url(base_url)
    admin_url = base.set(database="postgres")
    temp_db_name = f"uask_school_it_{uuid.uuid4().hex[:8]}"

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    except Exception as exc:
        pytest.skip(f"Could not create temporary PostgreSQL database: {exc}")
    finally:
        admin_engine.dispose()

    return str(base.set(database=temp_db_name))


def _drop_temp_database(db_url: str) -> None:
    parsed = make_url(db_url)
    db_name = parsed.database
    admin_url = parsed.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db_name AND pid <> pg_backend_pid()"
                ),
                {"db_name": db_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    finally:
        admin_engine.dispose()


def _write_fixture_csvs(tmp_path: Path) -> tuple[Path, Path]:
    ca_path = tmp_path / "ca.csv"
    us_path = tmp_path / "us.csv"
    ca_path.write_text(
        "\n".join(
            [
                "Source_ID,Facility_Name,Full_Addr,Street_No,Street_Name,City,Prov_Terr,Postal_Code,CSDNAME,CSDUID,Longitude,Latitude",
                "2001,École Test,10 Main St Montreal QC H2X1Y4,10,Main St,Montreal,QC,H2X 1Y4,Montreal,2466023,-73.56,45.50",
            ]
        ),
        encoding="utf-8",
    )
    us_path.write_text(
        "\n".join(
            [
                "School Name,State Name [Public School] Latest available year,State Abbr [Public School] Latest available year,School ID (12-digit) - NCES Assigned [Public School] Latest available year,Web Site URL [Public School] 2023-24,Location Address 1 [Public School] 2023-24,Location City [Public School] 2023-24,Location State Abbr [Public School] 2023-24,Location ZIP [Public School] 2023-24",
                "TEST HIGH SCHOOL,Texas,TX,999999999999,https://school.example.org,100 Campus Rd,Austin,TX,73301",
            ]
        ),
        encoding="utf-8",
    )
    return ca_path, us_path


def test_school_migration_and_dual_import_postgres(tmp_path: Path):
    db_url = _create_temp_database_url()
    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE school (
                        id SERIAL PRIMARY KEY,
                        country TEXT NOT NULL,
                        province_state TEXT NOT NULL,
                        district TEXT NULL,
                        city TEXT NULL,
                        school_name TEXT NOT NULL,
                        school_type TEXT NULL,
                        grade_range TEXT NULL,
                        external_id TEXT NULL,
                        source TEXT NOT NULL,
                        school_key TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP NULL,
                        updated_at TIMESTAMP NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE "user" (
                        id SERIAL PRIMARY KEY,
                        school_id INTEGER NULL REFERENCES school(id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO school (country, province_state, city, school_name, external_id, source, school_key)
                    VALUES ('USA', 'CA', 'Los Angeles', 'Legacy School', 'old-1', 'US_CSV', 'legacy-key-1')
                    """
                )
            )
            conn.execute(text('INSERT INTO "user" (school_id) VALUES (1)'))

        migration_summary = migrate_school_table(engine=engine, backfill_old_rows=True, create_trgm_index=False)
        assert migration_summary["backup_rows"] == 1
        assert migration_summary["backfilled_rows"] == 1

        ca_path, us_path = _write_fixture_csvs(tmp_path)
        with Session(engine) as session:
            first = import_school_csvs(session, ca_path, us_path)
            second = import_school_csvs(session, ca_path, us_path)

            count_all = session.exec(text("SELECT COUNT(*) FROM school")).one()[0]
            dedupe_count = session.exec(
                text(
                    "SELECT COUNT(*) FROM ("
                    "SELECT country, source, external_id, COUNT(*) c "
                    "FROM school GROUP BY country, source, external_id HAVING COUNT(*) > 1"
                    ") t"
                )
            ).one()[0]
            ca_row = session.exec(
                text("SELECT country, postal_code, csdname FROM school WHERE source = 'canada_csv' LIMIT 1")
            ).one()
            us_row = session.exec(
                text("SELECT country, website_url, address_line1 FROM school WHERE source = 'nces_csv' LIMIT 1")
            ).one()

        assert first["inserted"] == 2
        assert second["updated"] == 2
        assert count_all == 3
        assert dedupe_count == 0
        assert ca_row[0] == "CA"
        assert ca_row[1] == "H2X1Y4"
        assert ca_row[2] == "Montreal"
        assert us_row[0] == "US"
        assert us_row[1] == "https://school.example.org"
        assert us_row[2] == "100 Campus Rd"
    finally:
        engine.dispose()
        _drop_temp_database(db_url)
