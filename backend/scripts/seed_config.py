import sys
import os
from pathlib import Path
from sqlmodel import Session, select
from dotenv import load_dotenv

# Setup environment
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

env_path = backend_dir.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from app.database import engine
from app.models import SystemConfig

# Default configuration values - definitions only, not application logic
DEFAULT_CONFIG = {
    "tokens.text.input_max": (1800, "Max input tokens for text solve"),
    "tokens.text.input_max_chars": (3000, "Max input characters for text solve"),
    "tokens.text.output_max_minimal_solve": (700, "Max output tokens for minimal solve"),
    "tokens.text.output_max_minimal_study": (1200, "Max output tokens for minimal study"),
    "tokens.text.output_max_detailed_solve": (4500, "Max output tokens for detailed solve"),
    "tokens.text.output_max_detailed_study": (3500, "Max output tokens for detailed study"),
    "tokens.text.output_retry_cap_detailed_solve": (3200, "Retry max output tokens for detailed solve"),
    "tokens.text.output_retry_cap_detailed_study": (3600, "Retry max output tokens for detailed study"),
    "tokens.request.system_and_schema_budget": (3500, "Estimated system+schema tokens"),
    "tokens.request.expected_output_budget": (1200, "Expected output tokens for request fit"),
    "tokens.ocr_v5.output_max": (800, "Max output tokens for OCR v5"),
    "tokens.ocr_image.extract_max": (1800, "Max tokens for OCR image extraction"),
    "tokens.ocr_image.input_max": (1400, "Max input tokens for OCR image solve"),
    "tokens.ocr_image.input_overhead": (350, "Input overhead tokens for OCR image solve"),
    "tokens.ocr_pdf.extract_max": (3200, "Max tokens for OCR PDF extraction"),
    "tokens.ocr_pdf.input_max": (1800, "Max input tokens for OCR PDF solve"),
    "tokens.ocr_pdf.input_overhead": (450, "Input overhead tokens for OCR PDF solve"),
    "tokens.voice.input_max": (1200, "Max input tokens for voice solve"),
    "tokens.voice.input_overhead": (150, "Input overhead tokens for voice solve"),
}

def seed_config():
    print(f"Seeding SystemConfig table in DB: {os.environ.get('DATABASE_URL', 'default')}")
    with Session(engine) as session:
        for key, (default_val, desc) in DEFAULT_CONFIG.items():
            row = session.get(SystemConfig, key)
            if not row:
                print(f"Creating missing config: {key} = {default_val}")
                row = SystemConfig(key=key, value=str(default_val), description=desc)
                session.add(row)
            else:
                # Optional: Update description if missing
                if not row.description:
                    row.description = desc
                    session.add(row)
                pass # Do not overwrite existing values in a seed script (except initial)
        
        session.commit()
        print("Configuration seeding complete.")

if __name__ == "__main__":
    seed_config()
