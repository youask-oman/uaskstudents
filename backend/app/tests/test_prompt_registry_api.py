import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from app.api import admin_update_prompt_registry_prompt, PromptRegistryUpdateRequest
from app.models import PromptTemplateEntry


@pytest.mark.asyncio
async def test_admin_prompt_update_creates_new_version(tmp_path):
    db_path = tmp_path / "api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        req1 = PromptRegistryUpdateRequest(
            content="v1",
            tier="FREE",
            mode="SOLVE",
            role="DEVELOPER",
            updated_by="tester",
        )
        await admin_update_prompt_registry_prompt("solve_free_minimal_v1", req1, session)

        req2 = PromptRegistryUpdateRequest(
            content="v2",
            tier="FREE",
            mode="SOLVE",
            role="DEVELOPER",
            updated_by="tester",
        )
        await admin_update_prompt_registry_prompt("solve_free_minimal_v1", req2, session)

        rows = session.exec(
            select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == "solve_free_minimal_v1")
        ).all()
        assert len(rows) == 2
        active = [r for r in rows if r.is_active]
        assert len(active) == 1
        assert active[0].content == "v2"
