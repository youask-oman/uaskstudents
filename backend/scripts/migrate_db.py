"""
Database Migration Script
Drops all tables and recreates them with the latest schema,
then seeds with test data.
"""
from sqlmodel import SQLModel
from app.database import engine, create_db_and_tables
from app.models import User, ChatSession, ChatMessage, UsageLog, OCRJob
from scripts.seed_db import active_seed

def migrate_database():
    print("🔄 Starting database migration...")
    
    # Step 1: Drop all existing tables
    print("📦 Dropping all existing tables...")
    SQLModel.metadata.drop_all(engine)
    print("✅ Tables dropped successfully")
    
    # Step 2: Create tables with new schema
    print("🏗️  Creating tables with updated schema...")
    create_db_and_tables()
    print("✅ Tables created successfully")
    
    # Step 3: Seed the database
    print("🌱 Seeding database with test data...")
    active_seed()
    print("✅ Database seeded successfully")
    
    print("\n✨ Migration complete!")
    print("\n📝 Test Login Credentials:")
    print("   Email: student@uask.ai")
    print("   Password: student123")

if __name__ == "__main__":
    migrate_database()
