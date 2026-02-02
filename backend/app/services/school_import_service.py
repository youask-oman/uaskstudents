import csv
import hashlib
import itertools
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, select

from app.models import School

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

CA_PROVINCE_CODES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}

COUNTRY_ALIASES = {
    "US": "US",
    "USA": "US",
    "UNITED STATES": "US",
    "CA": "CA",
    "CANADA": "CA",
}


def normalize_country_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return COUNTRY_ALIASES.get(str(value).strip().upper())


def normalize_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text) or None


def normalize_address(value: Optional[str]) -> Optional[str]:
    return normalize_name(value)


def normalize_postal_code(country: str, value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    postal = str(value).strip()
    if not postal:
        return None
    if country == "CA":
        return postal.replace(" ", "").upper()
    return postal.replace(" ", "")


def parse_float_in_range(value: Optional[str], min_value: float, max_value: float) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if parsed < min_value or parsed > max_value:
        return None
    return parsed


def stable_school_key(country: str, source: str, external_id: str) -> str:
    raw = f"{country}|{source}|{external_id}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _row_value(row: Dict[str, str], candidates: Iterable[str]) -> Optional[str]:
    for key in candidates:
        if key in row and row[key] is not None:
            value = str(row[key]).strip()
            if value:
                return value
    return None


def map_canada_row(row: Dict[str, str]) -> Tuple[Optional[Dict], Optional[str]]:
    external_id = _clean(_row_value(row, ["Source_ID"]))
    school_name = _clean(_row_value(row, ["Facility_Name"]))
    city = _clean(_row_value(row, ["City"]))
    province = (_clean(_row_value(row, ["Prov_Terr"])) or "").upper()
    postal_code = normalize_postal_code("CA", _row_value(row, ["Postal_Code"]))

    if not external_id or not school_name or not city or not province:
        return None, "Missing one of required CA fields: Source_ID, Facility_Name, City, Prov_Terr"
    if province not in CA_PROVINCE_CODES:
        return None, f"Invalid CA province code: {province}"

    street_no = _clean(_row_value(row, ["Street_No"]))
    street_name = _clean(_row_value(row, ["Street_Name"]))
    address_line1 = None
    if street_no and street_name:
        address_line1 = f"{street_no} {street_name}".strip()

    full_address = _clean(_row_value(row, ["Full_Addr"]))
    normalized_address = normalize_address(
        " ".join(
            part for part in [address_line1, city, province, postal_code] if part
        )
    )

    payload = {
        "country": "CA",
        "province_state": province,
        "district": None,
        "city": city,
        "school_name": school_name,
        "school_type": None,
        "grade_range": None,
        "external_id": str(external_id),
        "source": "canada_csv",
        "school_key": stable_school_key("CA", "canada_csv", str(external_id)),
        "website_url": None,
        "address_line1": address_line1,
        "full_address": full_address,
        "street_no": street_no,
        "street_name": street_name,
        "postal_code": postal_code,
        "latitude": parse_float_in_range(_row_value(row, ["Latitude"]), -90.0, 90.0),
        "longitude": parse_float_in_range(_row_value(row, ["Longitude"]), -180.0, 180.0),
        "csdname": _clean(_row_value(row, ["CSDNAME"])),
        "csduid": _clean(_row_value(row, ["CSDUID"])),
        "normalized_name": normalize_name(school_name),
        "normalized_address": normalized_address,
        "updated_at": datetime.utcnow(),
    }
    return payload, None


def map_us_row(row: Dict[str, str]) -> Tuple[Optional[Dict], Optional[str]]:
    school_name = _clean(_row_value(row, ["School Name"]))
    external_id = _clean(
        _row_value(
            row,
            [
                "School ID (12-digit) - NCES Assigned",
                "School ID (12-digit) - NCES Assigned [Public School] Latest available year",
            ],
        )
    )
    city = _clean(_row_value(row, ["Location City", "Location City [Public School] 2023-24"]))
    province = (
        _clean(
            _row_value(
                row,
                [
                    "Location State Abbr",
                    "Location State Abbr [Public School] 2023-24",
                    "State Abbr",
                    "State Abbr [Public School] Latest available year",
                ],
            )
        )
        or ""
    ).upper()
    postal_code = normalize_postal_code("US", _row_value(row, ["Location ZIP", "Location ZIP [Public School] 2023-24"]))

    if not school_name or not external_id or not city or not province:
        return None, "Missing one of required US fields: School Name, School ID, Location City, Location State Abbr"
    if province not in US_STATE_CODES:
        return None, f"Invalid US state code: {province}"

    website_url = _clean(_row_value(row, ["Web Site URL", "Web Site URL [Public School] 2023-24"]))
    if website_url == "†":
        website_url = None

    address_line1 = _clean(_row_value(row, ["Location Address 1", "Location Address 1 [Public School] 2023-24"]))
    full_address = ", ".join(part for part in [address_line1, city, f"{province} {postal_code}".strip()] if part) or None
    normalized_address = normalize_address(
        " ".join(
            part for part in [address_line1, city, province, postal_code] if part
        )
    )

    payload = {
        "country": "US",
        "province_state": province,
        "district": None,
        "city": city,
        "school_name": school_name,
        "school_type": None,
        "grade_range": None,
        "external_id": str(external_id),
        "source": "nces_csv",
        "school_key": stable_school_key("US", "nces_csv", str(external_id)),
        "website_url": website_url,
        "address_line1": address_line1,
        "full_address": full_address,
        "street_no": None,
        "street_name": None,
        "postal_code": postal_code,
        "latitude": None,
        "longitude": None,
        "csdname": None,
        "csduid": None,
        "normalized_name": normalize_name(school_name),
        "normalized_address": normalized_address,
        "updated_at": datetime.utcnow(),
    }
    return payload, None


def _iter_csv_rows(csv_path: Path) -> Iterable[Dict[str, str]]:
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            return rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def _fetch_existing_keys(session: Session, records: List[Dict]) -> set:
    keys = [
        (r["country"], r["source"], r["external_id"])
        for r in records
        if r.get("external_id")
    ]
    if not keys:
        return set()
    existing = set()
    batch_size = 1000
    iterator = iter(keys)
    while True:
        chunk = list(itertools.islice(iterator, batch_size))
        if not chunk:
            break
        stmt = select(School.country, School.source, School.external_id).where(
            tuple_(School.country, School.source, School.external_id).in_(chunk)
        )
        existing.update(session.exec(stmt).all())
    return existing


def upsert_school_records(session: Session, records: List[Dict]) -> Dict[str, int]:
    if not records:
        return {"inserted": 0, "updated": 0}

    now = datetime.utcnow()
    normalized_records: List[Dict] = []
    for record in records:
        row = dict(record)
        row["updated_at"] = row.get("updated_at") or now
        normalized_records.append(row)

    # Postgres ON CONFLICT cannot target duplicated keys in the same INSERT statement.
    deduped: Dict[Tuple[str, str, str], Dict] = {}
    for row in normalized_records:
        key = (row.get("country"), row.get("source"), row.get("external_id"))
        if not all(key):
            continue
        deduped[key] = row
    normalized_records = list(deduped.values())

    existing = _fetch_existing_keys(session, normalized_records)
    inserted = 0
    updated = 0
    for rec in normalized_records:
        key = (rec.get("country"), rec.get("source"), rec.get("external_id"))
        if key in existing:
            updated += 1
        else:
            inserted += 1

    dialect = session.get_bind().dialect.name
    mutable_columns = [
        "province_state", "district", "city", "school_name", "school_type", "grade_range",
        "school_key", "website_url", "address_line1", "full_address", "street_no", "street_name",
        "postal_code", "latitude", "longitude", "csdname", "csduid",
        "normalized_name", "normalized_address", "updated_at",
    ]

    if dialect == "postgresql":
        batch_size = 1000
        for i in range(0, len(normalized_records), batch_size):
            chunk = normalized_records[i:i + batch_size]
            stmt = pg_insert(School).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["country", "source", "external_id"],
                set_={column: getattr(stmt.excluded, column) for column in mutable_columns},
            )
            session.exec(stmt)
    else:
        for record in normalized_records:
            existing_row = session.exec(
                select(School).where(
                    School.country == record["country"],
                    School.source == record["source"],
                    School.external_id == record["external_id"],
                )
            ).first()
            if existing_row:
                for column in mutable_columns:
                    setattr(existing_row, column, record.get(column))
                session.add(existing_row)
            else:
                session.add(School(**record))

    session.commit()
    return {"inserted": inserted, "updated": updated}


def import_school_csvs(session: Session, canada_csv_path: Path, us_csv_path: Path) -> Dict:
    stats = {
        "ca_rows_processed": 0,
        "us_rows_processed": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }
    records: List[Dict] = []

    if canada_csv_path.exists():
        for row in _iter_csv_rows(canada_csv_path):
            stats["ca_rows_processed"] += 1
            payload, error = map_canada_row(row)
            if error:
                stats["skipped"] += 1
                if len(stats["errors"]) < 25:
                    stats["errors"].append(f"CA row {stats['ca_rows_processed']}: {error}")
                continue
            records.append(payload)

    if us_csv_path.exists():
        for row in _iter_csv_rows(us_csv_path):
            stats["us_rows_processed"] += 1
            payload, error = map_us_row(row)
            if error:
                stats["skipped"] += 1
                if len(stats["errors"]) < 25:
                    stats["errors"].append(f"US row {stats['us_rows_processed']}: {error}")
                continue
            records.append(payload)

    upsert_stats = upsert_school_records(session, records)
    stats["inserted"] = upsert_stats["inserted"]
    stats["updated"] = upsert_stats["updated"]
    stats["error_count"] = len(stats["errors"])
    return stats
