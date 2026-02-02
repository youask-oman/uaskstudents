import pytest
from sqlmodel import Session
from app.database import engine, create_db_and_tables

@pytest.fixture(scope="session", autouse=True)
def init_db():
    create_db_and_tables()

@pytest.fixture(name="session")
def session_fixture():
    with Session(engine) as session:
        yield session
