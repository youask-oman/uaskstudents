from sqlmodel import Session, select, create_engine, text
from app.models import User
from app.database import engine

def migrate_profile_fields():
    print("Migrating Profile Fields...")
    
    with Session(engine) as session:
        # Check if columns exist (SQLite specific check, but flexible)
        try:
            # 1. Add is_public
            try:
                session.exec(text('ALTER TABLE "user" ADD COLUMN is_public BOOLEAN DEFAULT false'))
                print("Added is_public column")
            except Exception as e:
                print(f"is_public might already exist: {e}")

            # 2. Add last_active_at
            try:
                session.exec(text('ALTER TABLE "user" ADD COLUMN last_active_at TIMESTAMP'))
                print("Added last_active_at column")
            except Exception as e:
                print(f"last_active_at might already exist: {e}")

            # 3. Add learning_interests (JSON)
            try:
                # Check dialect
                dialect = session.bind.dialect.name
                col_type = "JSON"
                
                session.exec(text(f'ALTER TABLE "user" ADD COLUMN learning_interests {col_type}'))
                print(f"Added learning_interests column ({col_type})")
            except Exception as e:
                print(f"learning_interests might already exist: {e}")

            session.commit()
            print("Migration completed successfully.")
            
        except Exception as main_e:
            print(f"Migration failed: {main_e}")
            session.rollback()

if __name__ == "__main__":
    migrate_profile_fields()
