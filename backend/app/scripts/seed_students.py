#!/usr/bin/env python3
"""
Production-Quality Student Seeding Script

Creates 420 realistic student accounts with:
- IDs starting at 100 (sequential: 100-519)
- Password: password123 (hashed using app's pbkdf2_sha256)
- All required User model fields populated realistically
- Enterprise subscription tier
- Randomized location profiles (USA/Canada)

Usage:
    python -m app.scripts.seed_students --dry-run    # Preview without inserting
    python -m app.scripts.seed_students --commit     # Actually insert data
    python -m app.scripts.seed_students --test       # Run verification tests
    python -m app.scripts.seed_students --commit --test  # Seed + verify
"""

import sys
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select, text
from app.database import engine
from app.models import User
from app.auth import get_password_hash, verify_password


# ============================================================================
# CONSTANTS
# ============================================================================

STUDENT_PASSWORD = "password123"
STUDENT_COUNT = 420
START_ID = 100
END_ID = START_ID + STUDENT_COUNT - 1  # 519

# US States (50 + DC)
US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
    'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
    'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
    'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
    'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

# Canadian Provinces/Territories
CA_PROVINCES = [
    'ON', 'BC', 'AB', 'QC', 'SK', 'MB', 'NB', 'NS', 'PE', 'NL', 'YT', 'NT', 'NU'
]

# Academic levels
ACADEMIC_LEVELS = [
    "Middle School", "High School - Year 9", "High School - Year 10",
    "High School - Year 11", "High School - Year 12", "Undergraduate - Year 1",
    "Undergraduate - Year 2", "Undergraduate - Year 3", "Undergraduate - Year 4"
]

# Grade levels
GRADE_LEVELS = [f"Grade {i}" for i in range(1, 13)]

# Timezones
TIMEZONES = [
    "EST (UTC -5:00)", "CST (UTC -6:00)", "MST (UTC -7:00)", "PST (UTC -8:00)",
    "AST (UTC -4:00)", "NST (UTC -3:30)", "GMT (UTC +0:00)"
]

# Themes
THEMES = ["light", "dark", "auto"]

# Solving modes
SOLVING_MODES = ["Full Solution", "Hint Ladder", "Socratic"]

# First names for realistic names
FIRST_NAMES = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
    "Lucas", "Harper", "Henry", "Evelyn", "Alexander", "Abigail", "Michael",
    "Emily", "Daniel", "Ella", "Matthew", "Elizabeth", "Aiden", "Sofia",
    "Jackson", "Avery", "Sebastian", "Scarlett", "David", "Victoria",
    "Joseph", "Aria", "Samuel", "Grace", "Owen", "Chloe", "John", "Lily",
    "Ryan", "Layla", "Nathan", "Zoe", "Luke", "Penelope", "Andrew"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
]


# ============================================================================
# STUDENT GENERATION
# ============================================================================

def generate_random_date(days_ago_max: int = 90) -> datetime:
    """Generate a random datetime within the last N days."""
    days_ago = random.randint(0, days_ago_max)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    return datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)


def generate_student(student_id: int, password_hash: str) -> Dict[str, Any]:
    """Generate a single student record with all required fields."""
    
    # Realistic name
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f"{first_name} {last_name}"
    
    # Location - 60% USA, 40% Canada
    is_usa = random.random() < 0.60
    if is_usa:
        country = "USA"
        province_state = random.choice(US_STATES)
    else:
        country = "Canada"
        province_state = random.choice(CA_PROVINCES)
    
    # Created date (randomized within last 90 days)
    created_at = generate_random_date(90)
    last_active = generate_random_date(7)  # Active within last 7 days
    
    return {
        "id": student_id,
        "email": f"student{student_id}@uask.ai",
        "full_name": full_name,
        "password_hash": password_hash,
        "created_at": created_at,
        "role": "student",
        
        # Profile fields
        "academic_level": random.choice(ACADEMIC_LEVELS),
        "preferred_language": "English",
        "timezone": random.choice(TIMEZONES),
        "theme": random.choice(THEMES),
        "solving_mode": random.choice(SOLVING_MODES),
        
        # Enterprise subscription
        "subscription_tier": "enterprise",
        "subscription_status": "active",
        "subscription_expiry": datetime.utcnow() + timedelta(days=365),
        
        # Quotas (enterprise = unlimited)
        "quota_questions_total": 999999,
        "quota_scans_total": 999999,
        
        # Token tracking
        "tokens_used_this_month": random.randint(0, 50000),
        "last_token_reset": datetime.utcnow() - timedelta(days=random.randint(0, 30)),
        
        # Profile completeness
        "avatar_url": None,
        "bio": f"Student {student_id} - Learning with uask.ai",
        
        # Verification (all verified)
        "is_verified": True,
        "verification_token": None,
        
        # IP/Security (null for seeded users)
        "ip_address": None,
        "country": country,  # IP-detected country same as profile
        
        # Location Profile (for curriculum context)
        "profile_country": country,
        "profile_province_state": province_state,
        "grade_level": random.choice(GRADE_LEVELS),
        "school_id": None,  # No specific school assigned
        
        # Advanced profile
        "is_public": random.choice([True, False]),
        "learning_interests": None,
        "last_active_at": last_active,
        
        # Session security (null for seeded users)
        "session_token": None,
        "last_ip": None,
    }


def generate_all_students(password_hash: str) -> List[Dict[str, Any]]:
    """Generate all 420 student records."""
    students = []
    for i in range(STUDENT_COUNT):
        student_id = START_ID + i
        students.append(generate_student(student_id, password_hash))
    return students


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def clear_existing_students(session: Session, start_id: int, end_id: int) -> int:
    """Delete existing students in the ID range to allow re-seeding."""
    conn = session.connection()
    result = conn.execute(
        text('DELETE FROM "user" WHERE id >= :start AND id <= :end'),
        {"start": start_id, "end": end_id}
    )
    return result.rowcount if result else 0


def batch_insert_students(session: Session, students: List[Dict[str, Any]], batch_size: int = 100) -> int:
    """Insert students in batches for performance."""
    inserted = 0
    
    for i in range(0, len(students), batch_size):
        batch = students[i:i + batch_size]
        
        for student_data in batch:
            user = User(**student_data)
            session.add(user)
        
        session.flush()  # Flush batch to DB
        inserted += len(batch)
        print(f"  📦 Inserted batch {i // batch_size + 1}: {inserted}/{len(students)} students")
    
    return inserted


def reset_sequence(session: Session, next_id: int):
    """Reset the user ID sequence to start after seeded students."""
    # PostgreSQL specific - set sequence to continue after our seeded IDs
    conn = session.connection()
    conn.execute(text(f'SELECT setval(\'"user_id_seq"\', {next_id}, false)'))


# ============================================================================
# VERIFICATION TESTS
# ============================================================================

def run_verification_tests(session: Session) -> bool:
    """Run tests to verify seeding was successful."""
    print("\n" + "=" * 60)
    print("🧪 RUNNING VERIFICATION TESTS")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Count check
    print("\n📊 Test 1: Student count verification")
    conn = session.connection()
    result = conn.execute(
        text('SELECT COUNT(*) FROM "user" WHERE id >= :start AND id <= :end'),
        {"start": START_ID, "end": END_ID}
    )
    count = result.fetchone()[0]
    if count == STUDENT_COUNT:
        print(f"   ✅ PASS: Found exactly {count} students (expected {STUDENT_COUNT})")
    else:
        print(f"   ❌ FAIL: Found {count} students (expected {STUDENT_COUNT})")
        all_passed = False
    
    # Test 2: Password verification
    print("\n🔐 Test 2: Password hash verification")
    test_user = session.exec(select(User).where(User.id == START_ID)).first()
    if test_user:
        if verify_password(STUDENT_PASSWORD, test_user.password_hash):
            print(f"   ✅ PASS: Password 'password123' verified for student{START_ID}@uask.ai")
        else:
            print(f"   ❌ FAIL: Password verification failed for student{START_ID}")
            all_passed = False
    else:
        print(f"   ❌ FAIL: Could not find student with ID {START_ID}")
        all_passed = False
    
    # Test 3: All required fields populated
    print("\n📋 Test 3: Required fields check")
    sample_ids = [START_ID, START_ID + 100, START_ID + 200, START_ID + 300, END_ID]
    fields_ok = True
    for sid in sample_ids:
        user = session.exec(select(User).where(User.id == sid)).first()
        if user:
            missing = []
            if not user.email: missing.append("email")
            if not user.full_name: missing.append("full_name")
            if not user.password_hash: missing.append("password_hash")
            if not user.role: missing.append("role")
            if not user.subscription_tier: missing.append("subscription_tier")
            if not user.profile_country: missing.append("profile_country")
            if not user.profile_province_state: missing.append("profile_province_state")
            if not user.grade_level: missing.append("grade_level")
            
            if missing:
                print(f"   ❌ Student {sid} missing: {', '.join(missing)}")
                fields_ok = False
        else:
            print(f"   ❌ Student {sid} not found")
            fields_ok = False
    
    if fields_ok:
        print(f"   ✅ PASS: All sampled students have required fields")
    else:
        all_passed = False
    
    # Test 4: Enterprise subscription verification
    print("\n💼 Test 4: Enterprise subscription check")
    result = conn.execute(
        text('SELECT COUNT(*) FROM "user" WHERE id >= :start AND id <= :end AND subscription_tier = :tier'),
        {"start": START_ID, "end": END_ID, "tier": "enterprise"}
    )
    enterprise_count = result.fetchone()[0]
    if enterprise_count == STUDENT_COUNT:
        print(f"   ✅ PASS: All {enterprise_count} students have enterprise tier")
    else:
        print(f"   ❌ FAIL: Only {enterprise_count}/{STUDENT_COUNT} have enterprise tier")
        all_passed = False
    
    # Test 5: Location profile distribution
    print("\n🌍 Test 5: Location distribution check")
    result = conn.execute(
        text('SELECT profile_country, COUNT(*) FROM "user" WHERE id >= :start AND id <= :end GROUP BY profile_country'),
        {"start": START_ID, "end": END_ID}
    )
    distribution = {row[0]: row[1] for row in result.fetchall()}
    print(f"   📊 Distribution: {distribution}")
    if 'USA' in distribution and 'Canada' in distribution:
        print(f"   ✅ PASS: Both USA and Canada represented")
    else:
        print(f"   ❌ FAIL: Missing country representation")
        all_passed = False
    
    # Test 6: Email format check
    print("\n📧 Test 6: Email format verification")
    result = conn.execute(
        text('SELECT COUNT(*) FROM "user" WHERE id >= :start AND id <= :end AND email LIKE :pattern'),
        {"start": START_ID, "end": END_ID, "pattern": "student%@uask.ai"}
    )
    email_count = result.fetchone()[0]
    if email_count == STUDENT_COUNT:
        print(f"   ✅ PASS: All {email_count} emails match pattern student{{ID}}@uask.ai")
    else:
        print(f"   ❌ FAIL: Only {email_count}/{STUDENT_COUNT} match email pattern")
        all_passed = False
    
    # Test 7: ID range verification
    print("\n🔢 Test 7: ID range verification")
    result = conn.execute(
        text('SELECT MIN(id), MAX(id) FROM "user" WHERE id >= :start AND id <= :end'),
        {"start": START_ID, "end": END_ID}
    )
    row = result.fetchone()
    min_id, max_id = row[0], row[1]
    if min_id == START_ID and max_id == END_ID:
        print(f"   ✅ PASS: ID range is {min_id}-{max_id} (expected {START_ID}-{END_ID})")
    else:
        print(f"   ❌ FAIL: ID range is {min_id}-{max_id} (expected {START_ID}-{END_ID})")
        all_passed = False
    
    return all_passed


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Seed 420 student accounts for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m app.scripts.seed_students --dry-run     # Preview only
    python -m app.scripts.seed_students --commit      # Insert students
    python -m app.scripts.seed_students --test        # Run verification tests
    python -m app.scripts.seed_students --commit --test  # Seed and verify
        """
    )
    parser.add_argument("--dry-run", action="store_true", 
                        help="Preview what would be inserted (counts only, no PII)")
    parser.add_argument("--commit", action="store_true",
                        help="Actually insert the data")
    parser.add_argument("--test", action="store_true",
                        help="Run verification tests after seeding")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing students in ID range before seeding")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.commit and not args.test:
        parser.print_help()
        print("\n⚠️  Please specify --dry-run, --commit, or --test")
        sys.exit(1)
    
    print("=" * 60)
    print("🎓 STUDENT SEEDING SCRIPT")
    print("=" * 60)
    print(f"📊 Target: {STUDENT_COUNT} students")
    print(f"🔢 ID Range: {START_ID} - {END_ID}")
    print(f"🔐 Password: ****** (password123)")
    print(f"💼 Subscription: enterprise")
    print()
    
    # Generate password hash once (reused for all students)
    print("🔒 Generating password hash...")
    password_hash = get_password_hash(STUDENT_PASSWORD)
    print(f"   Hash generated (pbkdf2_sha256)")
    
    # Generate all student data
    print(f"\n📝 Generating {STUDENT_COUNT} student records...")
    students = generate_all_students(password_hash)
    print(f"   Generated {len(students)} records")
    
    # Analyze distribution (dry-run safe)
    usa_count = sum(1 for s in students if s["profile_country"] == "USA")
    canada_count = sum(1 for s in students if s["profile_country"] == "Canada")
    print(f"\n📊 Location Distribution:")
    print(f"   🇺🇸 USA: {usa_count} ({usa_count/len(students)*100:.1f}%)")
    print(f"   🇨🇦 Canada: {canada_count} ({canada_count/len(students)*100:.1f}%)")
    
    grade_dist = {}
    for s in students:
        grade = s["grade_level"]
        grade_dist[grade] = grade_dist.get(grade, 0) + 1
    print(f"\n📚 Grade Distribution:")
    for grade in sorted(grade_dist.keys(), key=lambda x: int(x.split()[-1])):
        print(f"   {grade}: {grade_dist[grade]}")
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("🏃 DRY RUN MODE - No changes made to database")
        print("=" * 60)
        print(f"\nWould insert {len(students)} students:")
        print(f"  - IDs: {START_ID} to {END_ID}")
        print(f"  - Emails: student{START_ID}@uask.ai to student{END_ID}@uask.ai")
        print(f"  - All with enterprise subscription")
        print(f"  - All with verified status")
        print(f"  - Randomized locations (USA/Canada)")
        print("\nTo actually insert, run with --commit flag")
        return
    
    if args.commit:
        print("\n" + "=" * 60)
        print("💾 COMMITTING TO DATABASE")
        print("=" * 60)
        
        with Session(engine) as session:
            conn = session.connection()
            # Check for existing students in range
            result = conn.execute(
                text('SELECT COUNT(*) FROM "user" WHERE id >= :start AND id <= :end'),
                {"start": START_ID, "end": END_ID}
            )
            existing = result.fetchone()[0]
            
            if existing > 0:
                if args.force:
                    print(f"\n⚠️  Found {existing} existing students in ID range")
                    print("   Deleting existing students (--force specified)...")
                    deleted = clear_existing_students(session, START_ID, END_ID)
                    print(f"   Deleted {deleted} existing records")
                    session.commit()
                else:
                    print(f"\n❌ ERROR: Found {existing} existing students in ID range {START_ID}-{END_ID}")
                    print("   Use --force to delete and re-seed, or choose a different ID range")
                    sys.exit(1)
            
            # Insert students in batches
            print(f"\n📥 Inserting {len(students)} students...")
            inserted = batch_insert_students(session, students, batch_size=100)
            
            # Reset sequence
            print(f"\n🔄 Resetting ID sequence to {END_ID + 1}...")
            reset_sequence(session, END_ID + 1)
            
            # Commit
            session.commit()
            print(f"\n✅ Successfully inserted {inserted} students!")
    
    if args.test:
        with Session(engine) as session:
            all_passed = run_verification_tests(session)
            
            print("\n" + "=" * 60)
            if all_passed:
                print("✅ ALL TESTS PASSED - ZERO ERRORS")
            else:
                print("❌ SOME TESTS FAILED - SEE ABOVE FOR DETAILS")
                sys.exit(1)
            print("=" * 60)


if __name__ == "__main__":
    main()
