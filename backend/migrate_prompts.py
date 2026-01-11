from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.begin() as conn:
        print("Adding 'slug' column to 'prompttemplate'...")
        try:
            conn.execute(text("ALTER TABLE prompttemplate ADD COLUMN slug VARCHAR"))
            conn.execute(text("CREATE UNIQUE INDEX ix_prompttemplate_slug ON prompttemplate (slug)"))
            print("Successfully added 'slug'.")
        except Exception as e:
            print(f"Skipping slug addition (might already exist): {e}")

        print("Renaming 'version_string' to 'version' in 'promptversion'...")
        try:
            conn.execute(text("ALTER TABLE promptversion RENAME COLUMN version_string TO version"))
            print("Successfully renamed 'version_string'.")
        except Exception as e:
            print(f"Skipping version rename (might already exist): {e}")

if __name__ == "__main__":
    migrate()
