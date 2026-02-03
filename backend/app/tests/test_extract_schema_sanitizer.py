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


def test_extract_payload_repairs_root_notation_and_unwraps_style_macros():
    payload = {
        "ok": True,
        "error": None,
        "is_math_page": True,
        "notes": [],
        "questions": [
            {
                "id": "q1",
                "page": 0,
                "text": r"\[ oot4 \of{\boldsymbol{x}^{2}-\boldsymbol{9}}-\boldsymbol{2}=0 \]",
                "type": "equation",
            }
        ],
    }
    normalized = _validate_extract_payload(payload, page_hint=0)
    question = normalized["questions"][0]
    assert r"\sqrt[4]{x^{2}-9}-2=0" in question["text"]
    assert question["latex"] == question["text"]


def test_extract_payload_populates_latex_when_text_looks_like_math():
    payload = {
        "ok": True,
        "error": None,
        "is_math_page": True,
        "notes": [],
        "questions": [
            {
                "id": "q1",
                "page": 0,
                "text": r"x=2\sqrt{x-1}",
                "latex": None,
                "type": "equation",
            }
        ],
    }
    normalized = _validate_extract_payload(payload, page_hint=0)
    question = normalized["questions"][0]
    assert question["latex"] == r"x=2\sqrt{x-1}"
