from app.database import engine
from app.models import SQLModel
import app.models # Ensure all models are registered

def sync():
    SQLModel.metadata.create_all(engine)
    print("Database synced successfully.")

if __name__ == "__main__":
    sync()
