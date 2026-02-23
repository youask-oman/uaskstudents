from app.rendering.render_events import build_render_events


def _sample_payload():
    return {
        "schema_name": "youask_math_openai_v1",
        "items": [
            {
                "question_id": "q1",
                "question_summary": "Solve x^2-1=0",
                "steps": [
                    {
                        "index": 1,
                        "title": "Factor",
                        "blocks": [
                            {"kind": "text", "content": "Factor the expression."},
                            {"kind": "math", "content": "x^2-1=(x-1)(x+1)", "display": True},
                        ],
                    }
                ],
                "final_answer": {"answer_text": "x=1 or x=-1", "answer_latex": "x=\\pm1", "values": []},
                "plot": {"should_visualize": False},
            }
        ],
    }


def test_render_events_order_and_end_marker():
    events, profile = build_render_events(_sample_payload(), seed="attempt-123")
    assert profile.seed == "attempt-123"
    assert len(events) > 0
    assert events[0].type == "MESSAGE_START"
    assert events[-1].type == "MESSAGE_END"
    assert [e.at_ms for e in events] == sorted([e.at_ms for e in events])


def test_render_events_deterministic_for_same_seed():
    left, _ = build_render_events(_sample_payload(), seed="attempt-123")
    right, _ = build_render_events(_sample_payload(), seed="attempt-123")
    assert [e.model_dump() for e in left] == [e.model_dump() for e in right]


def test_python_code_auto_generated_when_plot_exists_without_code():
    payload = _sample_payload()
    payload["items"][0]["plot"] = {
        "should_visualize": True,
        "recipe": {
            "title": "Auto code",
            "x_label": "N",
            "y_label": "Value",
            "expressions": ["a_n = (-1)^(n+1)/n^2 for n=1..20"],
            "domain": {"x_min": 1, "x_max": 20, "y_min": None, "y_max": None},
        },
        "python_code": None,
    }
    events, _ = build_render_events(payload, seed="attempt-123")
    python_events = [e for e in events if e.type == "PYTHON_CODE_SET"]
    assert len(python_events) == 1
    code = str(python_events[0].payload.get("code") or "")
    assert "import matplotlib.pyplot as plt" in code
    assert "ax.plot" in code
