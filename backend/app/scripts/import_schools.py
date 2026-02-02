"""
Usage:
    python -m app.scripts.import_schools --canada static_design/caschools.csv --us static_design/usschools.csv
"""

import argparse
from pathlib import Path

from sqlmodel import Session

from app.database import engine
from app.services.school_import_service import import_school_csvs


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CA + US schools into unified school table.")
    parser.add_argument("--canada", required=True, help="Path to Canada schools CSV file")
    parser.add_argument("--us", required=True, help="Path to US schools CSV file")
    args = parser.parse_args()

    ca_path = Path(args.canada).expanduser().resolve()
    us_path = Path(args.us).expanduser().resolve()

    if not ca_path.exists():
        raise FileNotFoundError(f"Canada CSV file not found: {ca_path}")
    if not us_path.exists():
        raise FileNotFoundError(f"US CSV file not found: {us_path}")

    with Session(engine) as session:
        stats = import_school_csvs(session, ca_path, us_path)

    print("School import finished")
    print(f"CA rows processed: {stats['ca_rows_processed']}")
    print(f"US rows processed: {stats['us_rows_processed']}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Updated: {stats['updated']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors captured: {stats['error_count']}")
    if stats["errors"]:
        print("First errors:")
        for msg in stats["errors"][:10]:
            print(f"- {msg}")


if __name__ == "__main__":
    main()

