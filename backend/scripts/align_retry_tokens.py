
from sqlmodel import Session, select
from app.database import engine
from app.models import PromptBinding

def align_retry_tokens():
    with Session(engine) as session:
        bindings = session.exec(select(PromptBinding)).all()
        print(f"Aligning retry tokens for {len(bindings)} bindings...")
        for b in bindings:
            if b.max_output_tokens and (b.json_retry_max_output_tokens is None or b.json_retry_max_output_tokens < b.max_output_tokens):
                print(f"Updating {b.tier.value}/{b.mode.value}: RetryTokens {b.json_retry_max_output_tokens} -> {b.max_output_tokens}")
                b.json_retry_max_output_tokens = b.max_output_tokens
                session.add(b)
        session.commit()
        print("Done.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    align_retry_tokens()
