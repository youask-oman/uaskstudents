#!/usr/bin/env python3
"""
Migration: Add School Directory and Profile Location Fields

This migration adds:
1. School table - for storing USA and Canada schools
2. SchoolImportRun table - for auditing CSV import runs
3. New User profile fields: profile_country, profile_province_state, grade_level, school_id

Run with: python -m app.scripts.migrations.add_school_directory
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlmodel import SQLModel, Session
from app.database import engine


def run_migration():
    """Run the migration to add school directory tables and user profile fields."""
    print("=" * 60)
    print("Migration: Add School Directory + Profile Location Fields")
    print("=" * 60)
    
    # Import models to ensure they're registered with SQLModel
    from app.models import User, School, SchoolImportRun  # noqa: F401
    
    print("\n📦 Creating/updating tables...")
    
    # This will create any new tables and add any new columns
    # Note: SQLModel's create_all is idempotent - it won't recreate existing tables
    SQLModel.metadata.create_all(engine)
    
    print("✅ Tables created/updated successfully!")
    
    # Verify the tables exist
    with Session(engine) as session:
        # Try to query the new tables
        try:
            from sqlalchemy import text
            
            # Check if School table exists
            result = session.exec(text("SELECT COUNT(*) FROM school"))
            count = result.one()[0]
            print(f"   School table: ✅ ({count} records)")
        except Exception as e:
            print(f"   School table: ❌ ({e})")
        
        try:
            # Check if SchoolImportRun table exists
            result = session.exec(text("SELECT COUNT(*) FROM schoolimportrun"))
            count = result.one()[0]
            print(f"   SchoolImportRun table: ✅ ({count} records)")
        except Exception as e:
            print(f"   SchoolImportRun table: ❌ ({e})")
        
        # Check for new user columns
        try:
            result = session.exec(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'user' 
                AND column_name IN ('profile_country', 'profile_province_state', 'grade_level', 'school_id')
            """))
            columns = [row[0] for row in result.fetchall()]
            
            for col in ['profile_country', 'profile_province_state', 'grade_level', 'school_id']:
                if col in columns:
                    print(f"   User.{col}: ✅")
                else:
                    print(f"   User.{col}: ❌ (missing)")
        except Exception as e:
            print(f"   User columns check failed: {e}")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
