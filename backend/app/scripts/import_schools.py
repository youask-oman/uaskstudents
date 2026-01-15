#!/usr/bin/env python3
"""
School Import Script - Imports USA and Canada school data from CSV files.

Usage:
    python -m app.scripts.import_schools --us data/schools_us.csv --ca data/schools_ca.csv --commit
    
Options:
    --us        Path to USA schools CSV file
    --ca        Path to Canada schools CSV file
    --commit    Actually write changes to database (otherwise dry-run)
    --reset     Delete all existing schools before import (default: false)
    --debug     Print detailed debug info for first 5 rows

CSV Field Mappings:
    USA: School Name, State Name, State Abbr, School ID (12-digit), City, etc.
    Canada: Source_ID, Facility_Name, City, Prov_Terr, etc.
"""

import argparse
import csv
import hashlib
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from app.database import engine
from app.models import School, SchoolImportRun


# --- Province/State Abbreviation Mappings ---
US_STATE_ABBREVS = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
    'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
    'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
    'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
    'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
    'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
    'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
    'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
    'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC',
    'PUERTO RICO': 'PR', 'GUAM': 'GU', 'AMERICAN SAMOA': 'AS', 'VIRGIN ISLANDS': 'VI',
}

CA_PROVINCE_ABBREVS = {
    'ALBERTA': 'AB', 'BRITISH COLUMBIA': 'BC', 'MANITOBA': 'MB',
    'NEW BRUNSWICK': 'NB', 'NEWFOUNDLAND AND LABRADOR': 'NL', 'NEWFOUNDLAND': 'NL',
    'NORTHWEST TERRITORIES': 'NT', 'NOVA SCOTIA': 'NS', 'NUNAVUT': 'NU',
    'ONTARIO': 'ON', 'PRINCE EDWARD ISLAND': 'PE', 'QUEBEC': 'QC',
    'SASKATCHEWAN': 'SK', 'YUKON': 'YT',
}


def normalize_text(text: Optional[str]) -> str:
    """Normalize text: strip, remove excess whitespace, handle unicode."""
    if not text:
        return ""
    # Normalize unicode (NFC form)
    text = unicodedata.normalize('NFC', str(text))
    # Replace multiple spaces with single space
    text = ' '.join(text.split())
    return text.strip()


def normalize_province_state(raw: str, country: str) -> str:
    """Normalize province/state abbreviation."""
    if not raw:
        return ""
    
    raw_upper = raw.strip().upper()
    
    # If already a 2-letter abbreviation, validate and return
    if len(raw_upper) == 2:
        if country == 'USA':
            # Check if valid state
            if raw_upper in US_STATE_ABBREVS.values():
                return raw_upper
        elif country == 'Canada':
            if raw_upper in CA_PROVINCE_ABBREVS.values():
                return raw_upper
        return raw_upper  # Return as-is even if not found
    
    # Try to map full name to abbreviation
    if country == 'USA':
        if raw_upper in US_STATE_ABBREVS:
            return US_STATE_ABBREVS[raw_upper]
    elif country == 'Canada':
        if raw_upper in CA_PROVINCE_ABBREVS:
            return CA_PROVINCE_ABBREVS[raw_upper]
    
    # Return first 2 chars as fallback for long names
    return raw_upper[:2] if len(raw_upper) >= 2 else raw_upper


def compute_school_key(country: str, province_state: str, city: str, school_name: str) -> str:
    """Compute stable SHA256-based deduplication key."""
    key_string = f"{country.lower()}|{province_state.lower()}|{(city or '').lower()}|{school_name.lower()}"
    return hashlib.sha256(key_string.encode('utf-8')).hexdigest()


def parse_us_row(row: Dict) -> Optional[Dict]:
    """Parse a row from the US schools CSV."""
    try:
        # Get school name
        school_name = normalize_text(row.get('School Name', ''))
        if not school_name:
            return None
        
        # Get state - try both possible columns
        state_abbr = normalize_text(row.get('State Abbr [Public School] Latest available year', ''))
        if not state_abbr:
            state_abbr = normalize_text(row.get('Location State Abbr [Public School] 2023-24', ''))
        
        state_name = normalize_text(row.get('State Name [Public School] Latest available year', ''))
        
        # Normalize the state
        province_state = normalize_province_state(state_abbr or state_name, 'USA')
        if not province_state:
            return None
        
        # Get city
        city = normalize_text(row.get('Location City [Public School] 2023-24', ''))
        
        # Get school ID (NCES ID)
        external_id = normalize_text(row.get('School ID (12-digit) - NCES Assigned [Public School] Latest available year', ''))
        
        school_key = compute_school_key('USA', province_state, city, school_name)
        
        return {
            'country': 'USA',
            'province_state': province_state,
            'city': city or None,
            'district': None,  # US CSV doesn't have district
            'school_name': school_name,
            'school_type': 'Public',  # File contains public schools
            'grade_range': None,
            'external_id': external_id or None,
            'source': 'US_CSV',
            'school_key': school_key,
        }
    except Exception as e:
        return None


def parse_ca_row(row: Dict) -> Optional[Dict]:
    """Parse a row from the Canada schools CSV."""
    try:
        # Get school name
        school_name = normalize_text(row.get('Facility_Name', ''))
        if not school_name:
            return None
        
        # Get province
        prov_terr = normalize_text(row.get('Prov_Terr', ''))
        province_state = normalize_province_state(prov_terr, 'Canada')
        if not province_state:
            return None
        
        # Get city
        city = normalize_text(row.get('City', ''))
        
        # Get source ID
        external_id = normalize_text(row.get('Source_ID', ''))
        
        # Get district (CSDNAME)
        district = normalize_text(row.get('CSDNAME', ''))
        
        school_key = compute_school_key('Canada', province_state, city, school_name)
        
        return {
            'country': 'Canada',
            'province_state': province_state,
            'city': city or None,
            'district': district or None,
            'school_name': school_name,
            'school_type': None,  # Not available in CSV
            'grade_range': None,
            'external_id': external_id or None,
            'source': 'CA_CSV',
            'school_key': school_key,
        }
    except Exception as e:
        return None


def import_schools(
    us_csv_path: Optional[str],
    ca_csv_path: Optional[str],
    commit: bool = False,
    reset: bool = False,
    debug: bool = False
) -> Dict:
    """
    Import schools from CSV files.
    
    Returns:
        Dict with import statistics
    """
    stats = {
        'us_rows_processed': 0,
        'ca_rows_processed': 0,
        'inserted_count': 0,
        'updated_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'errors_by_type': Counter(),
    }
    
    with Session(engine) as session:
        # Create import run record
        import_run = SchoolImportRun(
            started_at=datetime.utcnow(),
            status='running',
            reset_before_import=reset
        )
        if commit:
            session.add(import_run)
            session.commit()
            session.refresh(import_run)
        
        try:
            # Reset if requested
            if reset and commit:
                print("⚠️  Deleting all existing schools...")
                session.exec(select(School)).all()  # Force load
                from sqlalchemy import delete
                session.exec(delete(School))
                session.commit()
                print("✅ All schools deleted")
            
            # Track existing keys for upsert logic
            existing_keys = set()
            if not reset:
                existing_schools = session.exec(select(School.school_key)).all()
                existing_keys = {s for s in existing_schools}
                print(f"📊 Found {len(existing_keys)} existing schools in database")
            
            # Process US CSV
            if us_csv_path and Path(us_csv_path).exists():
                print(f"\n📁 Processing US schools: {us_csv_path}")
                with open(us_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        stats['us_rows_processed'] += 1
                        
                        if debug and i < 5:
                            print(f"  [DEBUG] Row {i+1}: {list(row.keys())[:5]}...")
                        
                        parsed = parse_us_row(row)
                        if not parsed:
                            stats['error_count'] += 1
                            stats['errors_by_type']['missing_required_field'] += 1
                            continue
                        
                        # Check for duplicate
                        if parsed['school_key'] in existing_keys:
                            stats['skipped_count'] += 1
                            continue
                        
                        # Insert
                        school = School(**parsed)
                        if commit:
                            session.add(school)
                        existing_keys.add(parsed['school_key'])
                        stats['inserted_count'] += 1
                        
                        # Commit in batches
                        if commit and stats['inserted_count'] % 1000 == 0:
                            session.commit()
                            print(f"  💾 Committed {stats['inserted_count']} schools...")
                
                print(f"✅ US: {stats['us_rows_processed']} rows processed")
            
            # Process Canada CSV
            if ca_csv_path and Path(ca_csv_path).exists():
                print(f"\n📁 Processing Canada schools: {ca_csv_path}")
                with open(ca_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        stats['ca_rows_processed'] += 1
                        
                        if debug and i < 5:
                            print(f"  [DEBUG] Row {i+1}: {list(row.keys())[:5]}...")
                        
                        parsed = parse_ca_row(row)
                        if not parsed:
                            stats['error_count'] += 1
                            stats['errors_by_type']['missing_required_field'] += 1
                            continue
                        
                        # Check for duplicate
                        if parsed['school_key'] in existing_keys:
                            stats['skipped_count'] += 1
                            continue
                        
                        # Insert
                        school = School(**parsed)
                        if commit:
                            session.add(school)
                        existing_keys.add(parsed['school_key'])
                        stats['inserted_count'] += 1
                        
                        # Commit in batches
                        if commit and stats['inserted_count'] % 1000 == 0:
                            session.commit()
                            print(f"  💾 Committed {stats['inserted_count']} schools...")
                
                print(f"✅ Canada: {stats['ca_rows_processed']} rows processed")
            
            # Final commit
            if commit:
                session.commit()
                
                # Update import run
                import_run.finished_at = datetime.utcnow()
                import_run.status = 'completed'
                import_run.us_rows_processed = stats['us_rows_processed']
                import_run.ca_rows_processed = stats['ca_rows_processed']
                import_run.inserted_count = stats['inserted_count']
                import_run.updated_count = stats['updated_count']
                import_run.skipped_count = stats['skipped_count']
                import_run.error_count = stats['error_count']
                import_run.errors_json = dict(stats['errors_by_type'])
                session.add(import_run)
                session.commit()
        
        except Exception as e:
            if commit:
                import_run.finished_at = datetime.utcnow()
                import_run.status = 'failed'
                import_run.errors_json = {'fatal_error': str(e)}
                session.add(import_run)
                session.commit()
            raise
    
    return stats


def print_report(stats: Dict, commit: bool):
    """Print import summary report."""
    print("\n" + "=" * 60)
    print("📊 IMPORT SUMMARY REPORT")
    print("=" * 60)
    
    if not commit:
        print("⚠️  DRY RUN - No changes were written to database")
        print("   Run with --commit to persist changes")
    
    print(f"\n📁 Files Processed:")
    print(f"   US rows:     {stats['us_rows_processed']:,}")
    print(f"   Canada rows: {stats['ca_rows_processed']:,}")
    print(f"   TOTAL:       {stats['us_rows_processed'] + stats['ca_rows_processed']:,}")
    
    print(f"\n📈 Results:")
    print(f"   Inserted: {stats['inserted_count']:,}")
    print(f"   Updated:  {stats['updated_count']:,}")
    print(f"   Skipped:  {stats['skipped_count']:,} (duplicates)")
    print(f"   Errors:   {stats['error_count']:,}")
    
    if stats['errors_by_type']:
        print(f"\n❌ Errors by Type:")
        for error_type, count in stats['errors_by_type'].most_common(10):
            print(f"   {error_type}: {count:,}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Import school data from CSV files')
    parser.add_argument('--us', type=str, help='Path to US schools CSV')
    parser.add_argument('--ca', type=str, help='Path to Canada schools CSV')
    parser.add_argument('--commit', action='store_true', help='Actually write to database')
    parser.add_argument('--reset', action='store_true', help='Delete all existing schools first')
    parser.add_argument('--debug', action='store_true', help='Print debug info')
    
    args = parser.parse_args()
    
    if not args.us and not args.ca:
        parser.error("At least one of --us or --ca must be provided")
    
    print("🏫 School Import Script")
    print("=" * 60)
    
    try:
        stats = import_schools(
            us_csv_path=args.us,
            ca_csv_path=args.ca,
            commit=args.commit,
            reset=args.reset,
            debug=args.debug
        )
        print_report(stats, args.commit)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
