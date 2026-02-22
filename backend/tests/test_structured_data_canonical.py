from app.api import _build_canonical_structured_data, _enforce_plot_in_payload, _extract_canonical_final_answer


def test_enforce_plot_sets_recipe_when_graph_on():
    payload = {
        "items": [
            {
                "question_id": "q1",
                "steps": [],
                "final_answer": {"answer_text": "x=1", "answer_latex": "x=1"},
                "plot": {"should_visualize": False, "decision_reason": "Plot omitted", "recipe": None},
            }
        ]
    }
    out = _enforce_plot_in_payload(
        payload,
        graph_mode="on",
        tasks=[{"task_id": "t1", "task_text": "Plot the graph", "order_index": 1}],
        question_text="plot on x ∈ [-2, 6], y ∈ [-2, 10]",
    )
    plot = out["items"][0]["plot"]
    assert plot["should_visualize"] is True
    assert isinstance(plot.get("recipe"), dict)
    assert plot["recipe"].get("x_range") == [-2.0, 6.0]


def test_extract_canonical_final_answer_prefers_structured_final_answer():
    item = {
        "final_answer": {"answer_text": "(3,1)", "answer_latex": "\\boxed{(3,1)}", "values": [], "units": None},
        "steps": [
            {"index": 1, "explanation": "begin_final wrong end_final", "math_latex": ["wrong"]},
        ],
    }
    out = _extract_canonical_final_answer(item)
    assert out["answer_latex"] == "\\boxed{(3,1)}"


def test_build_canonical_structured_data_excludes_legacy_duplicate_keys():
    canonical = _build_canonical_structured_data(
        runtime_questions_json=[
            {
                "question_id": "q1",
                "question_text": "Q1 text",
                "mode": "SOLVE",
                "graph_mode": "on",
                "domain_mode": "reals",
            }
        ],
        safe_items=[
            {
                "question_id": "q1",
                "steps": [{"index": 1, "explanation": "step", "math_latex": []}],
                "final_answer": {"answer_text": "x=1", "answer_latex": "x=1", "values": [], "units": None},
                "plot": {"should_visualize": True, "recipe": {"kind": "function_2d"}},
            }
        ],
        task_parse={
            "tasks": [{"task_id": "t1", "task_text": "Solve", "order_index": 1}],
            "selected_task_ids": ["t1"],
        },
        workload_billing={"estimated_total_credits": 1, "charged_total_credits": 1},
        telemetry={"request_id": "r1", "attempt_id": "a1", "provider": "ollama", "model": "m1"},
        body_tier="SHORT_STEPS",
        request_id="r1",
        attempt_id="a1",
        requested_mode="general",
    )
    forbidden = {"questions", "solutions", "problem", "raw_user_extraction", "final_answers", "final_answer"}
    assert not (forbidden & set(canonical.keys()))
    assert canonical["question"]["text"] == "Q1 text"
    assert canonical["tasks"][0]["task_id"] == "t1"
    assert canonical["solution"]["final_answer"]["answer_text"] == "x=1"
