from sqlmodel import Session, select
from app.database import engine
from app.models import PromptTemplateEntry, JsonSchemaEntry

def list_registry():
    with Session(engine) as session:
        print("--- Prompts ---")
        prompts = session.exec(select(PromptTemplateEntry)).all()
        for p in prompts:
            print(f"ID: {p.prompt_id} | Role: {p.role} | Mode: {p.mode} | Tier: {p.tier} | Version: {p.version} | Active: {p.is_active}")
            print(f"Content Preview: {p.content[:100]}...")
            print("-" * 20)

        print("\n--- Schemas ---")
        schemas = session.exec(select(JsonSchemaEntry)).all()
        for s in schemas:
            print(f"ID: {s.schema_id} | Version: {s.version} | Active: {s.is_active}")
            # print(f"Content: {s.content}")
            print("-" * 20)

if __name__ == "__main__":
    list_registry()
