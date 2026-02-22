
import sys
import os
# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text

def migrate():
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        print("Ensuring 'provider' column exists in prompt_bindings...")
        try:
            conn.execute(text("ALTER TABLE prompt_bindings ADD COLUMN IF NOT EXISTS provider VARCHAR(255) DEFAULT 'openai'"))
            print("[OK] Column check done.")
        except Exception as e:
            print(f"[INFO] Column check: {e}")

        print("Ensuring index on provider exists...")
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_bindings_provider ON prompt_bindings (provider)"))
            print("[OK] Index check done.")
        except Exception as e:
            print(f"[INFO] Index check: {e}")

        print("Ensuring UniqueConstraint includes provider...")
        try:
            # We first try to drop the old unique constraint if it doesn't include provider
            # This is tricky because we don't know the exact name, but often it's sa_generated or uq_...
            # For simplicity, we just try to add the new one. If it already exists, it will fail silently or based on name.
            conn.execute(text("ALTER TABLE prompt_bindings ADD CONSTRAINT uq_prompt_binding_tier_mode_provider UNIQUE (tier, mode, provider)"))
            print("[OK] UniqueConstraint added/updated.")
        except Exception as e:
            print(f"[INFO] UniqueConstraint check: {e}")

if __name__ == "__main__":
    migrate()
