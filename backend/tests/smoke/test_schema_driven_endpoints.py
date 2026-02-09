import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import get_password_hash
from app.database import engine
from app.main import app
from app.models import User
from app.prompts.db_loader import resolve_prompt_bundle
from scripts.seed_production import run_seed


def _ensure_user() -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "schema-smoke@uask.ai")).first()
        if not user:
            user = User(
                email="schema-smoke@uask.ai",
                full_name="Schema Smoke",
                password_hash=get_password_hash("SchemaSmoke123!"),
                is_verified=True,
                role="student",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return int(user.id)


def _resolve_modes() -> None:
    with Session(engine) as session:
        resolve_prompt_bundle(provider="openai", tier="standard", mode="solve", db_session=session)
        resolve_prompt_bundle(provider="openai", tier="research", mode="solve", db_session=session)
        resolve_prompt_bundle(provider="openai", tier="standard", mode="plot_spec", db_session=session)


def test_schema_driven_endpoints_no_500s():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)

    _resolve_modes()
    user_id = _ensure_user()
    client = TestClient(app)

    fake_solver = MagicMock()
    fake_solver.solve = AsyncMock(
        return_value={
            "solution": {"final_answer": "ok"},
            "telemetry": {"prompt_binding": {"global_system_prompt_id": "x", "developer_prompt_id": "y"}},
        }
    )
    with patch("app.services.solver_v3.get_solver_v3", return_value=fake_solver):
        for tier in ("standard", "research"):
            resp = client.post(
                "/api/v1/solve",
                json={"text": "What is 2+2?", "tier": tier, "requested_mode": "text"},
                headers={"X-User-ID": str(user_id)},
            )
            assert resp.status_code != 500, f"{tier} solve returned 500: {resp.text}"

        plot_resp = client.post(
            "/api/v1/solve",
            json={"text": "Plot y=x^2", "tier": "standard", "requested_mode": "text", "graph_mode": "on"},
            headers={"X-User-ID": str(user_id)},
        )
        assert plot_resp.status_code != 500, f"plot solve returned 500: {plot_resp.text}"
