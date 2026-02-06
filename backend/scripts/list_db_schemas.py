
from sqlmodel import Session, select
from app.database import engine
from app.models import JsonSchemaEntry

def list_schemas():
    with Session(engine) as session:
        schemas = session.exec(select(JsonSchemaEntry).where(JsonSchemaEntry.is_active == True)).all()
        print(f"Found {len(schemas)} active schemas:")
        for s in schemas:
            print(f"ID: {s.schema_id}")
            print(f"Name in Content: {s.content.get('name')}")
            print("-" * 20)

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    list_schemas()
