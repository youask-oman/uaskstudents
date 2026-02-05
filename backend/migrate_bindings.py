from sqlalchemy import text
from app.database import engine

def migrate():
    columns = [
        ("max_input_tokens", "INTEGER"),
        ("system_schema_budget_tokens", "INTEGER"),
        ("context_budget_tokens", "INTEGER"),
        ("json_retry_max_output_tokens", "INTEGER"),
        ("json_retry_max_attempts", "INTEGER"),
        ("timeout_ms", "INTEGER"),
        ("temperature", "DOUBLE PRECISION"),
        ("top_p", "DOUBLE PRECISION"),
        ("plot_points_cap", "INTEGER"),
        ("plot_traces_cap", "INTEGER"),
        ("plot_annotations_cap", "INTEGER"),
        ("trim_strategy", "VARCHAR"),
    ]

    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                # Use sub-transaction or separate execution to avoid block-level failure
                print(f"Adding {col_name}...")
                conn.execute(text(f"ALTER TABLE prompt_bindings ADD COLUMN {col_name} {col_type} DEFAULT NULL"))
                conn.commit()
                print(f"Successfully added {col_name}")
            except Exception as e:
                # If column already exists, it will fail, which is fine
                # psycopg2.errors.DuplicateColumn is what we expect
                print(f"Skipping {col_name}: {e}")
                # conn.rollback() # Not needed with commit inside loop or if we want to continue

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
