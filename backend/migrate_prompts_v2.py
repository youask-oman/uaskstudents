from app.database import engine
from sqlalchemy import text, inspect

def migrate():
    inspector = inspect(engine)
    with engine.begin() as conn:
        # Check and add 'slug' to 'prompttemplate'
        columns = [c['name'] for c in inspector.get_columns('prompttemplate')]
        if 'slug' not in columns:
            print("Adding 'slug' column to 'prompttemplate'...")
            conn.execute(text("ALTER TABLE prompttemplate ADD COLUMN slug VARCHAR"))
            conn.execute(text("CREATE UNIQUE INDEX ix_prompttemplate_slug ON prompttemplate (slug)"))
            print("Successfully added 'slug'.")
        else:
            print("'slug' column already exists in 'prompttemplate'.")

        # Check and rename 'version_string' to 'version' in 'promptversion'
        columns_v = [c['name'] for c in inspector.get_columns('promptversion')]
        if 'version_string' in columns_v and 'version' not in columns_v:
            print("Renaming 'version_string' to 'version' in 'promptversion'...")
            conn.execute(text("ALTER TABLE promptversion RENAME COLUMN version_string TO version"))
            print("Successfully renamed 'version_string'.")
        elif 'version' in columns_v:
            print("'version' column already exists in 'promptversion'.")
        else:
            print("No 'version_string' found to rename in 'promptversion'.")

if __name__ == "__main__":
    migrate()
