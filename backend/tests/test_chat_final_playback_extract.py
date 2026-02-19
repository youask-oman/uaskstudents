from types import SimpleNamespace

from app.api import _extract_assistant_content_for_playback


def _msg(structured_data, content=""):
    return SimpleNamespace(
        structured_data=structured_data,
        content=content,
        role="assistant",
    )


def test_extract_playback_prefers_solutions_and_strips_markers():
    msg = _msg(
        {
            "solutions": [
                {
                    "question_id": "q1",
                    "steps": [
                        {"index": 1, "explanation": "BEGIN_SOLUTION Use Bayes theorem END_STEPS"},
                    ],
                    "final_answer": {"answer_text": "0.3896"},
                }
            ],
            "raw_user_extraction": {
                "sections": [
                    {"heading": "Question Q1", "steps": [{"index": 1, "raw": "BROKEN"}]}
                ]
            },
        },
        content="0.9513",
    )

    out = _extract_assistant_content_for_playback(msg)
    assert "Use Bayes theorem" in out
    assert "BROKEN" not in out
    assert "BEGIN_SOLUTION" not in out


def test_extract_playback_uses_solution_final_answer_not_global_final():
    msg = _msg(
        {
            "global_final_answer": "2*0.03",
            "solutions": [
                {
                    "question_id": "q2",
                    "steps": [{"index": 1, "explanation": "Compute posterior."}],
                    "final_answer": {"answer_latex": r"\boxed{0.9513}", "answer_text": "0.9513"},
                }
            ],
        }
    )
    out = _extract_assistant_content_for_playback(msg)
    assert r"\boxed{0.9513}" in out
    assert "2*0.03" not in out

