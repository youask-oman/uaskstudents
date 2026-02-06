
from sqlmodel import Session, select
from app.database import engine
from app.models import JsonSchemaEntry
import json

def fix_schemas():
    with Session(engine) as session:
        schemas = session.exec(select(JsonSchemaEntry).where(JsonSchemaEntry.is_active == True)).all()
        print(f"Fixing {len(schemas)} active schemas...")
        for s in schemas:
            old_name = s.content.get("name")
            # New name: use ID but strip .schema.json and replace other dots with underscore
            new_name = s.schema_id.replace(".schema.json", "").replace(".", "_")
            
            if old_name != new_name:
                print(f"Updating {s.schema_id}: {old_name} -> {new_name}")
                # Create a copy to trigger update
                new_content = dict(s.content)
                new_content["name"] = new_name
                s.content = new_content
                session.add(s)
        
        session.commit()
        print("Done.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    fix_schemas()
