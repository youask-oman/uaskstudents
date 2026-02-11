from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
import pytest

from app.api_admin_ocr_config import router as admin_ocr_config_router
from app.database import get_session
from app.admin_billing.deps import get_admin_user
from app.models import User, PromptTemplateEntry, JsonSchemaEntry, PromptModeEnum, PromptRoleEnum


fastapi_app = FastAPI()
fastapi_app.include_router(admin_ocr_config_router)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session

    def get_admin_override():
        user = session.exec(select(User).where(User.email == "admin@test.com")).first()
        if not user:
            user = User(email="admin@test.com", full_name="Admin", password_hash="x", role="admin")
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    fastapi_app.dependency_overrides[get_session] = get_session_override
    fastapi_app.dependency_overrides[get_admin_user] = get_admin_override
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()


def _seed_prompt_and_schema(session: Session) -> None:
    prompt = PromptTemplateEntry(
        prompt_id="openai_ocr_system_prompt_v1.txt",
        mode=PromptModeEnum.OCR_EXTRACT,
        role=PromptRoleEnum.DEVELOPER,
        content="Test OCR prompt",
        version=1,
        is_active=True,
        updated_by="test",
    )
    schema = JsonSchemaEntry(
        schema_id="openai_image_extract_v1.schema.json",
        content={"name": "openai_image_extract_v1", "schema": {"type": "object"}},
        version=1,
        is_active=True,
        updated_by="test",
    )
    session.add(prompt)
    session.add(schema)
    session.commit()


def test_ocr_config_validation_disables_all_engines(client):
    res = client.put(
        "/api/admin/ocr-configuration",
        json={"local_engine_enabled": False, "openai_engine_enabled": False, "reason": "testing"},
    )
    assert res.status_code == 422


def test_ocr_config_update_success(client, session):
    _seed_prompt_and_schema(session)
    payload = {
        "reason": "Enable OCR config",
        "local_engine_enabled": True,
        "openai_engine_enabled": True,
        "openai_model": "gpt-5-mini",
        "openai_system_prompt_key": "openai_ocr_system_prompt_v1.txt",
        "openai_schema_key": "openai_image_extract_v1.schema.json",
        "dedupe_window_hours": 24,
        "ocr_hold_ttl_minutes": 10,
        "rate_limit_extract_per_min": 10,
        "local_ocr_credit": 2,
        "openai_ocr_credit": 3,
        "solve_credit": 3,
    }
    res = client.put("/api/admin/ocr-configuration", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["config"]["openai_system_prompt_key"] == "openai_ocr_system_prompt_v1.txt"
