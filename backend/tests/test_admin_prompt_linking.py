
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from fastapi.testclient import TestClient
from app.api import api_router
import app.models as app_models
from app.models import Plan, PlanPromptLink, User
# We don't need PromptAsset directly if we use app_models.PromptAsset
from app.database import get_session
from app.llm_profiles.profile_resolver import ProfileResolver

# Setup minimal app for testing
from fastapi import FastAPI
fastapi_app = FastAPI()
fastapi_app.include_router(api_router)

@pytest.fixture(name="session")
def session_fixture():
    from sqlmodel.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session
    fastapi_app.dependency_overrides[get_session] = get_session_override
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()

def test_admin_prompt_linking_flow(client, session):
    # 1. Setup Data: Plan and Assets
    plan = Plan(name="TestPlan", slug="test_plan", credits_per_month=100, price_monthly_cents=1000, price_yearly_cents=0)
    session.add(plan)
    
    asset1 = app_models.PromptAsset(key="asset_1", kind="system", path="path/1", checksum="1")
    asset2 = app_models.PromptAsset(key="asset_2", kind="schema", path="path/2", checksum="2")
    asset3 = app_models.PromptAsset(key="asset_3", kind="system", path="path/3", checksum="3") # Alternate system
    
    session.add(asset1)
    session.add(asset2)
    session.add(asset3)
    session.commit()
    
    # 2. Test GET /admin/prompt-assets
    response = client.get("/admin/prompt-assets")
    assert response.status_code == 200
    assets_json = response.json()
    assert len(assets_json) == 3
    # Sort or find by key to be deterministic
    asset_1_json = next(a for a in assets_json if a["key"] == "asset_1")
    assert asset_1_json["kind"] == "system"

    # 3. Test PUT /admin/plans/{id}/prompt-links (Assign Initial)
    payload = {
        "minimal": {
            "system_asset_id": asset1.id,
            "schema_asset_id": asset2.id
        }
    }
    response = client.put(f"/admin/plans/{plan.id}/prompt-links", json=payload)
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    
    # 3.5 Test GET /admin/plans/{id}/prompt-links
    response = client.get(f"/admin/plans/{plan.id}/prompt-links")
    assert response.status_code == 200
    links_json = response.json()
    assert links_json["minimal"]["system_asset_id"] == asset1.id
    assert links_json["minimal"]["schema_asset_id"] == asset2.id
    assert links_json["detailed"] == {} # Should be empty
    
    # Verify DB
    link = session.exec(select(PlanPromptLink).where(PlanPromptLink.plan_id == plan.id, PlanPromptLink.mode == "minimal")).first()
    assert link is not None
    assert link.system_prompt_asset_id == asset1.id
    
    # 4. Verify Resolution Logic sees the link
    # (Mock AssetLoader to avoid file error)
    from app.llm_profiles.asset_loader import AssetLoader
    original_get = AssetLoader.get_asset_content
    AssetLoader.get_asset_content = lambda x: {} if x.kind == "schema" else f"CONTENT:{x.key}"
    
    try:
        profile = ProfileResolver.resolve_profile(session, None, requested_mode="minimal", force_tier="test_plan")
        assert "CONTENT:asset_1" in profile.system_prompt_content
        
        # 5. Re-Assign to Asset 3 (Update)
        payload_update = {
            "minimal": {
                "system_asset_id": asset3.id, # Change system prompt
                "schema_asset_id": asset2.id
            }
        }
        response = client.put(f"/admin/plans/{plan.id}/prompt-links", json=payload_update)
        assert response.status_code == 200
        
        session.refresh(link)
        assert link.system_prompt_asset_id == asset3.id
        
        # Verify resolution picks up new asset
        profile_new = ProfileResolver.resolve_profile(session, None, requested_mode="minimal", force_tier="test_plan")
        assert "CONTENT:asset_3" in profile_new.system_prompt_content
        
    finally:
        AssetLoader.get_asset_content = original_get
