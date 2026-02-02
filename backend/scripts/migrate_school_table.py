from app.database import engine
from app.services.school_migration_service import migrate_school_table


def main() -> None:
    summary = migrate_school_table(engine=engine, backfill_old_rows=True, create_trgm_index=True)
    print("School table migration complete.")
    print(f"Backed up rows to school_legacy: {summary['backup_rows']}")
    print(f"Backfilled rows into new school table: {summary['backfilled_rows']}")


if __name__ == "__main__":
    main()

