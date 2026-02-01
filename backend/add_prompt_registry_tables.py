from sqlmodel import create_engine, text
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_migration():
    is_sqlite = "sqlite" in DATABASE_URL
    json_type = "JSON" if is_sqlite else "JSONB"

    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id VARCHAR PRIMARY KEY,
            prompt_id VARCHAR NOT NULL,
            tier VARCHAR NULL,
            mode VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            content TEXT NOT NULL,
            version INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR NULL
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_templates_prompt_id_version ON prompt_templates (prompt_id, version)",
        "CREATE INDEX IF NOT EXISTS idx_prompt_templates_active ON prompt_templates (prompt_id, is_active)",
        f"""
        CREATE TABLE IF NOT EXISTS json_schemas (
            id VARCHAR PRIMARY KEY,
            schema_id VARCHAR NOT NULL,
            content {json_type} NOT NULL,
            version INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR NULL
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_json_schemas_schema_id_version ON json_schemas (schema_id, version)",
        "CREATE INDEX IF NOT EXISTS idx_json_schemas_active ON json_schemas (schema_id, is_active)",
        f"""
        CREATE TABLE IF NOT EXISTS prompt_bindings (
            id VARCHAR PRIMARY KEY,
            tier VARCHAR NOT NULL,
            mode VARCHAR NOT NULL,
            global_system_prompt_id VARCHAR NOT NULL,
            developer_prompt_id VARCHAR NOT NULL,
            output_schema_id VARCHAR NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_prompt_bindings_active ON prompt_bindings (tier, mode, is_active)",
    ]

    for stmt in statements:
        try:
            with engine.connect() as conn:
                print(f"Executing: {stmt.strip().splitlines()[0]}")
                conn.execute(text(stmt))
                conn.commit()
        except Exception as e:
            print(f"Skipped/Failed: {e}")

if __name__ == "__main__":
    run_migration()
