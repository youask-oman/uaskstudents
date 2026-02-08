import sys
import os
from sqlmodel import Session, select
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(env_path)

# Force Postgres URL to bypass poisoned shell config
os.environ["DATABASE_URL"] = "postgresql://uask_user:uask_password@localhost:5432/uask_db"

from app.database import engine, DATABASE_URL
from app.models import PromptBinding, PromptTierEnum, PromptModeEnum

def update_tokens():
    print(f"DATABASE_URL used: {DATABASE_URL}")
    print(f"Connecting to DB via app.database engine...")
    with Session(engine) as session:
        # Find binding for STANDARD / SOLVE
        # Note: Enum values might be strictly typed or strings depending on SQLModel version, using Enums is safer.
        statement = select(PromptBinding).where(
            PromptBinding.tier == PromptTierEnum.STANDARD,
            PromptBinding.mode == PromptModeEnum.SOLVE
        )
        results = session.exec(statement).all()
        
        if not results:
            print("No binding found for STANDARD / SOLVE")
            # Try strings if Enums fail to match (though SQLModel handles this usually)
            return

        for binding in results:
            print(f"Updating binding {binding.id}...")
            print(f"  Old max_output_tokens: {binding.max_output_tokens}")
            binding.max_output_tokens = 4000
            session.add(binding)
        
        session.commit()
        print("Successfully updated max_output_tokens to 4000.")

if __name__ == "__main__":
    update_tokens()
