from app.api import _render_batch_display_markdown, _reconcile_batch_solutions_with_questions


def test_render_batch_display_markdown_includes_all_questions_and_math():
    questions = [
        {"question_id": "q1", "question_text": "Positive on first test"},
        {"question_id": "q2", "question_text": "Positive on both tests"},
        {"question_id": "q3", "question_text": "Find E[X] and SD[X]"},
        {"question_id": "q4", "question_text": "Explain interpretation"},
    ]
    solutions = [
        {
            "question_id": "q1",
            "steps": [
                {
                    "explanation": "Use Bayes theorem.",
                    "math_latex": [r"P(D \mid T_1)=\frac{P(T_1 \mid D)P(D)}{P(T_1)}"],
                }
            ],
            "final_answer": {"answer_text": "0.3896"},
        },
        {"question_id": "q2", "steps": [{"explanation": "Update posterior with two positives."}], "final_answer": {"answer_text": "0.9513"}},
        {"question_id": "q3", "steps": [{"explanation": "Compute unconditional binomial moments."}], "final_answer": {"answer_text": "E[X]=0.0964, SD[X]=0.3026"}},
        {"question_id": "q4", "steps": [{"explanation": "Explain prevalence mixture."}], "final_answer": {"answer_text": "Not equal to 2*0.94 nor 2*0.03"}},
    ]

    markdown = _render_batch_display_markdown(questions, solutions)

    assert "### Q1 (q1)" in markdown
    assert "### Q2 (q2)" in markdown
    assert "### Q3 (q3)" in markdown
    assert "### Q4 (q4)" in markdown
    assert "P(D \\mid T_1)" in markdown
    assert markdown.strip() != "0.9513"


def test_reconcile_batch_solutions_uses_question_ids_not_array_position():
    questions = [
        {"question_id": "q1", "question_text": "Question 1"},
        {"question_id": "q2", "question_text": "Question 2"},
    ]
    payload_items = [
        {"question_id": "q2", "final_answer": {"answer_text": "two"}},
        {"question_id": "q1", "final_answer": {"answer_text": "one"}},
    ]

    reconciled, diag = _reconcile_batch_solutions_with_questions(questions, payload_items)

    assert diag["ok"] is True
    assert [item["question_id"] for item in reconciled] == ["q1", "q2"]
    assert reconciled[0]["final_answer"]["answer_text"] == "one"
    assert reconciled[1]["final_answer"]["answer_text"] == "two"
