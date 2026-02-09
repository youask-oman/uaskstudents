import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from app.main import app
import json

client = TestClient(app, raise_server_exceptions=True)

@pytest.fixture
def mock_solver_v3():
    with patch("app.services.solver_v3.get_solver_v3") as mock:
        solver_instance = MagicMock()
        solver_instance.solve = AsyncMock()
        mock.return_value = solver_instance
        yield solver_instance

@pytest.fixture
def mock_plot_pipeline():
    with patch("app.services.plot_integration.maybe_generate_plot", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_billing():
    with patch("app.services.billing_service.billing_service") as mock:
        mock.initiate_hold.return_value = MagicMock()
        mock.finalize_transaction.return_value = MagicMock()
        yield mock

@pytest.fixture
def mock_subscription():
    with patch("app.services.subscription_service.subscription_service") as mock:
        sub = MagicMock()
        sub.id = 1
        mock.get_or_create_subscription.return_value = sub
        yield mock

@pytest.fixture
def mock_db():
    with patch("app.api.get_session") as mock:
        session = MagicMock()
        mock.return_value = session
        yield session

@pytest.fixture
def mock_user(mock_db):
    user = MagicMock()
    user.id = 1
    user.profile_country = "Canada"
    user.profile_province_state = "ON"
    user.grade_level = "10"
    mock_db.get.return_value = user
    return user

def test_solve_v3_graph_mode_off(mock_solver_v3, mock_plot_pipeline, mock_user, mock_billing, mock_subscription):
    # Mock LLM response that wants a plot
    mock_solver_v3.solve.return_value = {
        "problem": {"original_text": "y=x^2", "normalized_text": "y=x^2", "detected_tasks": ["graph"]},
        "classification": {"grade_band": "9-10", "domain": "algebra", "topic": "quadratics", "difficulty": "easy"},
        "refusal": {"is_refusal": False},
        "assumptions": [],
        "steps": [],
        "final_answer": {"answer_text": "Done", "answer_latex": "Done", "values": []},
        "visuals": {
            "should_visualize": True,
            "decision_reason": "LLM wants plot",
            "plots": [{"plot_id": "llm_plot", "title": "LLM Plot"}]
        },
        "quality": {"confidence": 0.9, "common_mistakes": []}
    }
    
    # Mock pipeline (doesn't matter because it's forced OFF)
    mock_plot_pipeline.return_value = {"plot_generated": False}

    response = client.post("/api/v1/solve_v3?user_id=1", json={
        "text_query": "y=x^2",
        "graph_mode": "off"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["visuals"]["should_visualize"] is False
    assert data["visuals"]["plots"] == []
    assert "Forced OFF" in data["visuals"]["decision_reason"]

def test_solve_v3_graph_mode_on_llm_fails_fallback_triggered(mock_solver_v3, mock_plot_pipeline, mock_user, mock_billing, mock_subscription):
    # Mock LLM response that DOES NOT want a plot
    mock_solver_v3.solve.return_value = {
        "problem": {"original_text": "y=x^2", "normalized_text": "y=x^2", "detected_tasks": ["graph"]},
        "classification": {"grade_band": "9-10", "domain": "algebra", "topic": "quadratics", "difficulty": "easy"},
        "refusal": {"is_refusal": False},
        "assumptions": [],
        "steps": [],
        "final_answer": {"answer_text": "Done", "answer_latex": "Done", "values": []},
        "visuals": {
            "should_visualize": False,
            "decision_reason": "LLM thinks no plot needed",
            "plots": []
        },
        "quality": {"confidence": 0.9, "common_mistakes": []}
    }
    
    # Mock pipeline successful fallback
    mock_plot_pipeline.return_value = {
        "plot_generated": True,
        "spec": {
            "plot_id": "plot_matplotlib_fallback",
            "plotly_json": {"data": [{"x": [1, 2], "y": [3, 4]}], "layout": {"title": "Fallback"}},
        },
        "pipeline_type": "matplotlib_fallback"
    }

    response = client.post("/api/v1/solve_v3?user_id=1", json={
        "text_query": "y=x^2 graph-on",
        "graph_mode": "on"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["visuals"]["should_visualize"] is True
    assert len(data["visuals"]["plots"]) == 1
    assert data["visuals"]["plots"][0]["plot_id"] == "plot_matplotlib_fallback"
    assert "Forced ON" in data["visuals"]["decision_reason"]

def test_solve_v3_graph_mode_auto_positive(mock_solver_v3, mock_plot_pipeline, mock_user, mock_billing, mock_subscription):
    # LLM says NO plot
    mock_solver_v3.solve.return_value = {
        "problem": {"original_text": "y=x^2", "normalized_text": "y=x^2", "detected_tasks": ["graph"]},
        "classification": {"grade_band": "9-10", "domain": "algebra", "topic": "quadratics", "difficulty": "easy"},
        "refusal": {"is_refusal": False},
        "steps": [],
        "final_answer": {"answer_text": "Done", "answer_latex": "Done", "values": []},
        "assumptions": [],
        "visuals": {"should_visualize": False, "decision_reason": "No", "plots": []},
        "quality": {"confidence": 0.9, "common_mistakes": []}
    }
    
    # But pipeline generated one anyway (maybe heuristic was positive)
    mock_plot_pipeline.return_value = {
        "plot_generated": True,
        "spec": {
            "plot_id": "auto_plot",
            "plotly_json": {"data": [], "layout": {}}
        }
    }

    response = client.post("/api/v1/solve_v3?user_id=1", json={
        "text_query": "y=x^2 graph-auto",
        "graph_mode": "auto"
    })

    assert response.status_code == 200
    data = response.json()
    # In 'auto' mode, if plot is generated, we force should_visualize = True
    assert data["visuals"]["should_visualize"] is True
    assert len(data["visuals"]["plots"]) == 1
