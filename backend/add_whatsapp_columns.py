"""
Add WhatsApp integration fields to User model
Run this script to update existing database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import engine
from sqlalchemy import text
import secrets
import string

def generate_whatsapp_secret():
    """Generate a 8-character alphanumeric code"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

def run_migration():
    """Add WhatsApp columns to users table"""
    with engine.begin() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user' AND column_name = 'whatsapp_number'
        """))
        
        if result.fetchone():
            print("WhatsApp columns already exist. Skipping migration.")
            return
        
        print("Adding WhatsApp columns to user table...")
        
        # Add whatsapp_number column
        conn.execute(text("""
            ALTER TABLE "user" 
            ADD COLUMN whatsapp_number VARCHAR NULL
        """))
        
        # Add whatsapp_secret column
        conn.execute(text("""
            ALTER TABLE "user" 
            ADD COLUMN whatsapp_secret VARCHAR NULL
        """))
        
        # Add whatsapp_enabled column
        conn.execute(text("""
            ALTER TABLE "user" 
            ADD COLUMN whatsapp_enabled BOOLEAN DEFAULT TRUE
        """))
        
        # Create index on whatsapp_number
        conn.execute(text("""
            CREATE INDEX ix_user_whatsapp_number ON "user" (whatsapp_number)
        """))
        
        print("✓ Columns added successfully")
        
        # Generate secret codes for existing users
        print("Generating WhatsApp secret codes for existing users...")
        
        result = conn.execute(text("SELECT id FROM \"user\""))
        user_ids = [row[0] for row in result]
        
        for user_id in user_ids:
            secret = generate_whatsapp_secret()
            conn.execute(
                text("UPDATE \"user\" SET whatsapp_secret = :secret WHERE id = :id"),
                {"secret": secret, "id": user_id}
            )
        
        print(f"✓ Generated secret codes for {len(user_ids)} users")
        print("\nMigration completed successfully!")

if __name__ == "__main__":
    run_migration()
