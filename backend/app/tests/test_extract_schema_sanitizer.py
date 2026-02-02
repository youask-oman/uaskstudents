from app.api import _validate_extract_payload


def test_extract_payload_trims_whitespace_keys_and_adds_note():
    payload = {
        "ok": True,
        "error": None,
        "is_math_page": True,
        "notes": [],
        " questions ": [
            {
                " id ": "q1",
                " page ": 0,
                " text ": "Solve x+1=2",
                " latex ": "x+1=2",
                " type ": "equation",
            }
        ],
    }
    normalized = _validate_extract_payload(payload, page_hint=0)
    assert normalized["ok"] is True
    assert "questions" in normalized
    assert len(normalized["questions"]) == 1
    assert any("Sanitized whitespace in JSON keys before validation." in n for n in normalized["notes"])
