from sqlmodel import Session, create_engine, select

from app.models import School
from app.services.school_import_service import (
    map_canada_row,
    map_us_row,
    parse_float_in_range,
    upsert_school_records,
)


def test_map_canada_row_with_accents():
    row = {
        "Source_ID": "1466",
        "Facility_Name": "École Joseph-Moreau",
        "Full_Addr": "9750 - 74 Avenue Edmonton AB T6E1E8",
        "Street_No": "9750",
        "Street_Name": "74 avenue",
        "City": "Edmonton",
        "Prov_Terr": "AB",
        "Postal_Code": "T6E 1E8",
        "CSDNAME": "Edmonton",
        "CSDUID": "4811061",
        "Longitude": "-113.4812940",
        "Latitude": "53.51064300",
    }

    payload, error = map_canada_row(row)
    assert error is None
    assert payload["country"] == "CA"
    assert payload["source"] == "canada_csv"
    assert payload["external_id"] == "1466"
    assert payload["postal_code"] == "T6E1E8"
    assert payload["normalized_name"] == "ecole joseph moreau"
    assert payload["latitude"] == 53.510643
    assert payload["longitude"] == -113.481294


def test_map_us_row_basic_mapping():
    row = {
        "School Name": "ABERNETHY ELEMENTARY SCHOOL",
        "School ID (12-digit) - NCES Assigned [Public School] Latest available year": "411004000865",
        "Web Site URL [Public School] 2023-24": "http://www.pps.net/schools/abernethy",
        "Location Address 1 [Public School] 2023-24": "2421 SE Orange Ave",
        "Location City [Public School] 2023-24": "Portland",
        "Location State Abbr [Public School] 2023-24": "OR",
        "Location ZIP [Public School] 2023-24": "97214",
    }

    payload, error = map_us_row(row)
    assert error is None
    assert payload["country"] == "US"
    assert payload["source"] == "nces_csv"
    assert payload["external_id"] == "411004000865"
    assert payload["website_url"] == "http://www.pps.net/schools/abernethy"
    assert payload["full_address"] == "2421 SE Orange Ave, Portland, OR 97214"


def test_external_id_and_postal_code_are_text():
    row = {
        "School Name": "Text Field Test School",
        "School ID (12-digit) - NCES Assigned [Public School] Latest available year": "000012340000",
        "Location City [Public School] 2023-24": "Austin",
        "Location State Abbr [Public School] 2023-24": "TX",
        "Location ZIP [Public School] 2023-24": "078901",
        "Location Address 1 [Public School] 2023-24": "1 Main St",
    }
    payload, error = map_us_row(row)
    assert error is None
    assert isinstance(payload["external_id"], str)
    assert payload["external_id"] == "000012340000"
    assert isinstance(payload["postal_code"], str)
    assert payload["postal_code"] == "078901"


def test_lat_lon_range_validation():
    assert parse_float_in_range("45.0", -90, 90) == 45.0
    assert parse_float_in_range("-181", -180, 180) is None
    assert parse_float_in_range("91", -90, 90) is None
    assert parse_float_in_range("not-a-number", -90, 90) is None


def test_upsert_conflict_updates_mutable_fields():
    engine = create_engine("sqlite://")
    School.__table__.create(engine)

    base = {
        "country": "US",
        "province_state": "CA",
        "district": None,
        "city": "Los Angeles",
        "school_name": "Old Name",
        "school_type": None,
        "grade_range": None,
        "external_id": "123456789012",
        "source": "nces_csv",
        "school_key": "stable-key-1",
        "website_url": None,
        "address_line1": "10 Main St",
        "full_address": "10 Main St, Los Angeles, CA 90001",
        "street_no": None,
        "street_name": None,
        "postal_code": "90001",
        "latitude": None,
        "longitude": None,
        "csdname": None,
        "csduid": None,
        "normalized_name": "old name",
        "normalized_address": "10 main st los angeles ca 90001",
    }

    updated = dict(base)
    updated["school_name"] = "New Name"
    updated["website_url"] = "https://example.org"
    updated["normalized_name"] = "new name"

    with Session(engine) as session:
        stats1 = upsert_school_records(session, [base])
        stats2 = upsert_school_records(session, [updated])
        rows = session.exec(select(School)).all()

    assert stats1 == {"inserted": 1, "updated": 0}
    assert stats2 == {"inserted": 0, "updated": 1}
    assert len(rows) == 1
    assert rows[0].school_name == "New Name"
    assert rows[0].website_url == "https://example.org"

