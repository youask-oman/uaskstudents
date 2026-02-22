from app.services.solve.single_task_parser import parse_single_question_tasks, unicode_integrity_probe


def test_parse_single_question_tasks_assigns_t_ids():
    text = (
        "Q1) Example\n"
        "Tasks:\n"
        "1) First\n"
        "2) Second\n"
        "3) Third\n"
    )
    out = parse_single_question_tasks(text, max_tasks=15)
    assert out["has_tasks_header"] is True
    assert out["detected_task_count_raw"] == 3
    assert out["task_count_capped"] == 3
    assert [t["task_id"] for t in out["tasks"]] == ["t1", "t2", "t3"]


def test_parse_single_question_tasks_caps_at_15():
    lines = [f"{i}) Task {i}" for i in range(1, 21)]
    text = "Q1) Example\nTasks:\n" + "\n".join(lines)
    out = parse_single_question_tasks(text, max_tasks=15)
    assert out["detected_task_count_raw"] == 20
    assert out["task_count_capped"] == 15
    assert out["omitted_count"] == 5
    assert out["tasks"][-1]["task_id"] == "t15"


def test_unicode_integrity_probe_keeps_math_symbols():
    text = "x ∈ [-4, 4], y ≤ 13, μ=50, σ=8, 12 − x²"
    out = unicode_integrity_probe(text)
    assert out["unicode_integrity_check"] is True
    assert "?" not in text
