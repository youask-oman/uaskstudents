import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from app.api import (
    admin_activate_prompt_registry_binding,
    admin_delete_prompt_registry_binding,
    admin_delete_prompt_registry_schema,
    admin_delete_prompt_registry_prompt,
    admin_list_prompt_registry_prompts,
    admin_list_prompt_registry_schemas,
    admin_update_prompt_registry_schema,
    admin_update_prompt_registry_prompt,
    BindingActivateRequest,
    PromptRegistryUpdateRequest,
    SchemaRegistryUpdateRequest,
)
from app.models import JsonSchemaEntry, PromptBinding, PromptTemplateEntry


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


@pytest.mark.asyncio
async def test_admin_prompt_delete_removes_all_versions(tmp_path):
    db_path = tmp_path / "api_delete.db"
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

        result = await admin_delete_prompt_registry_prompt("solve_free_minimal_v1", "tester", session)

        rows = session.exec(
            select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == "solve_free_minimal_v1")
        ).all()
        assert result.status == "ok"
        assert result.deleted_versions == 2
        assert rows == []


@pytest.mark.asyncio
async def test_admin_schema_delete_removes_all_versions(tmp_path):
    db_path = tmp_path / "api_schema_delete.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        req1 = SchemaRegistryUpdateRequest(
            content={"type": "object", "title": "v1"},
            updated_by="tester",
        )
        await admin_update_prompt_registry_schema("schema_to_delete_v1", req1, session)

        req2 = SchemaRegistryUpdateRequest(
            content={"type": "object", "title": "v2"},
            updated_by="tester",
        )
        await admin_update_prompt_registry_schema("schema_to_delete_v1", req2, session)

        result = await admin_delete_prompt_registry_schema("schema_to_delete_v1", "tester", session)

        rows = session.exec(
            select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id == "schema_to_delete_v1")
        ).all()
        assert result.status == "ok"
        assert result.deleted_versions == 2
        assert rows == []


@pytest.mark.asyncio
async def test_admin_schema_update_accepts_openai_wrapper(tmp_path):
    db_path = tmp_path / "api_schema_wrapper.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    wrapped = {
        "type": "json_schema",
        "json_schema": {
            "name": "wrapped_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    }

    with Session(engine) as session:
        result = await admin_update_prompt_registry_schema(
            "wrapped_schema_v1",
            SchemaRegistryUpdateRequest(content=wrapped, updated_by="tester"),
            session,
        )
        rows = session.exec(
            select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id == "wrapped_schema_v1")
        ).all()
        assert result.schema_id == "wrapped_schema_v1"
        assert len(rows) == 1
        assert rows[0].content.get("type") == "object"


@pytest.mark.asyncio
async def test_admin_binding_delete_removes_row(tmp_path):
    db_path = tmp_path / "api_binding_delete.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        await admin_update_prompt_registry_prompt(
            "global_system_prompt_v1",
            PromptRegistryUpdateRequest(
                content="GLOBAL",
                tier=None,
                mode="SOLVE",
                role="SYSTEM",
                updated_by="tester",
            ),
            session,
        )
        await admin_update_prompt_registry_prompt(
            "solve_free_minimal_v1",
            PromptRegistryUpdateRequest(
                content="DEV",
                tier="FREE",
                mode="SOLVE",
                role="DEVELOPER",
                updated_by="tester",
            ),
            session,
        )
        await admin_update_prompt_registry_schema(
            "youask_math_solver_response_v1",
            SchemaRegistryUpdateRequest(
                content={"type": "object", "title": "schema"},
                updated_by="tester",
            ),
            session,
        )
        binding = await admin_activate_prompt_registry_binding(
            BindingActivateRequest(
                tier="FREE",
                mode="SOLVE",
                global_system_prompt_id="global_system_prompt_v1",
                developer_prompt_id="solve_free_minimal_v1",
                output_schema_id="youask_math_solver_response_v1",
                updated_by="tester",
            ),
            session,
        )

        result = await admin_delete_prompt_registry_binding(binding.id, session)
        rows = session.exec(select(PromptBinding).where(PromptBinding.id == binding.id)).all()
        assert result.status == "ok"
        assert rows == []


@pytest.mark.asyncio
async def test_admin_prompt_list_include_inactive_shows_inactive_ids(tmp_path):
    db_path = tmp_path / "api_prompt_include_inactive.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        await admin_update_prompt_registry_prompt(
            "inactive_prompt_v1",
            PromptRegistryUpdateRequest(
                content="v1",
                tier="FREE",
                mode="SOLVE",
                role="DEVELOPER",
                updated_by="tester",
            ),
            session,
        )

        rows = session.exec(
            select(PromptTemplateEntry).where(PromptTemplateEntry.prompt_id == "inactive_prompt_v1")
        ).all()
        rows[0].is_active = False
        session.add(rows[0])
        session.commit()

        active_only = await admin_list_prompt_registry_prompts(include_inactive=False, db=session)
        include_inactive = await admin_list_prompt_registry_prompts(include_inactive=True, db=session)
        assert all(item.prompt_id != "inactive_prompt_v1" for item in active_only)
        match = [item for item in include_inactive if item.prompt_id == "inactive_prompt_v1"]
        assert len(match) == 1
        assert match[0].is_active is False


@pytest.mark.asyncio
async def test_admin_schema_list_include_inactive_shows_inactive_ids(tmp_path):
    db_path = tmp_path / "api_schema_include_inactive.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        await admin_update_prompt_registry_schema(
            "inactive_schema_v1",
            SchemaRegistryUpdateRequest(
                content={"type": "object"},
                updated_by="tester",
            ),
            session,
        )

        rows = session.exec(
            select(JsonSchemaEntry).where(JsonSchemaEntry.schema_id == "inactive_schema_v1")
        ).all()
        rows[0].is_active = False
        session.add(rows[0])
        session.commit()

        active_only = await admin_list_prompt_registry_schemas(include_inactive=False, db=session)
        include_inactive = await admin_list_prompt_registry_schemas(include_inactive=True, db=session)
        assert all(item.schema_id != "inactive_schema_v1" for item in active_only)
        match = [item for item in include_inactive if item.schema_id == "inactive_schema_v1"]
        assert len(match) == 1
        assert match[0].is_active is False
