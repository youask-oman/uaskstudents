#!/usr/bin/env python3
"""Add user profile location columns to existing user table."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database import engine

def add_columns():
    print("Adding new columns to user table...")
    
    with engine.connect() as conn:
        # Add profile_country
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS profile_country TEXT'))
            print("  ✅ Added profile_country")
        except Exception as e:
            print(f"  ⚠️ profile_country: {e}")
        
        # Add profile_province_state
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS profile_province_state TEXT'))
            print("  ✅ Added profile_province_state")
        except Exception as e:
            print(f"  ⚠️ profile_province_state: {e}")
        
        # Add grade_level
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS grade_level TEXT'))
            print("  ✅ Added grade_level")
        except Exception as e:
            print(f"  ⚠️ grade_level: {e}")
        
        # Add school_id (FK to school table)
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS school_id INTEGER'))
            print("  ✅ Added school_id")
        except Exception as e:
            print(f"  ⚠️ school_id: {e}")
        
        # Create index on school_id
        try:
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_user_school_id ON "user" (school_id)'))
            print("  ✅ Created index on school_id")
        except Exception as e:
            print(f"  ⚠️ Index: {e}")
        
        conn.commit()
    
    print("\n✅ All columns added successfully!")

if __name__ == "__main__":
    add_columns()
