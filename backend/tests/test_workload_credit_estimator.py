from app.services.workload_credit_estimator import estimate_task_bundle_credits


def test_simple_no_tasks_implicit_minimum():
    out = estimate_task_bundle_credits(
        context_text="3(x-2)=15",
        tasks=[],
        selected_task_ids=[],
    )
    assert out["selected_task_ids"] == ["t1"]
    assert out["estimated_total_credits"] >= 1


def test_graph_task_costs_more_than_basic_task():
    tasks = [
        {"task_id": "t1", "task_text": "Find the domain.", "order_index": 1},
        {"task_id": "t2", "task_text": "Plot with grid legend and title and mark points.", "order_index": 2},
    ]
    out = estimate_task_bundle_credits(
        context_text="f(x)=x^2",
        tasks=tasks,
        selected_task_ids=["t1", "t2"],
    )
    assert out["per_task_credits"]["t2"] > out["per_task_credits"]["t1"]
    assert out["estimated_total_credits"] >= 1


def test_unicode_roundtrip_not_mutated():
    text = "x ∈ [-4, 4], y ≤ 13, μ=50, σ=8, √x, π"
    out = estimate_task_bundle_credits(
        context_text=text,
        tasks=[{"task_id": "t1", "task_text": text, "order_index": 1}],
        selected_task_ids=["t1"],
    )
    assert "?" not in text
    assert out["selected_task_ids"] == ["t1"]
