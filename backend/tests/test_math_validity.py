import json
from pathlib import Path

from app.services.validation.math_validity import assess_math_validity


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "math_validity"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_clean_mcq_sqrt_ratio_confidence_high():
    payload = _load_fixture("clean_mcq_ratio_sqrt.json")
    out = assess_math_validity(payload)
    assert out["is_valid_math_problem"] is True
    assert out["normalized_question"]["kind"] == "mcq"
    assert isinstance(out["normalized_question"]["choices"], dict)
    assert len(out["normalized_question"]["choices"]) >= 4
    assert out["confidence_percent"] > 80


def test_choices_do_not_become_standalone_questions():
    payload = _load_fixture("clean_mcq_ratio_sqrt.json")
    out = assess_math_validity(payload)
    stem = out["normalized_question"]["stem"]
    assert "(a)" not in stem.lower()
    assert out["normalized_question"]["choices"]["a"]


def test_free_response_algebra_valid():
    payload = _load_fixture("free_response_algebra.json")
    out = assess_math_validity(payload)
    assert out["normalized_question"]["kind"] == "free_response"
    assert out["is_valid_math_problem"] is True
    assert out["confidence_percent"] >= 45


def test_graph_text_valid():
    payload = _load_fixture("graph_text.json")
    out = assess_math_validity(payload)
    assert out["is_valid_math_problem"] is True
    assert out["confidence_percent"] >= 45


def test_table_text_valid():
    payload = _load_fixture("table_text.json")
    out = assess_math_validity(payload)
    assert out["is_valid_math_problem"] is True
    assert out["confidence_percent"] >= 45


def test_noisy_ocr_triggers_low_confidence_warning():
    payload = _load_fixture("noisy_ocr.json")
    out = assess_math_validity(payload)
    assert "LOW_CONFIDENCE" in out["warnings"]
    assert out["confidence_percent"] < 50


def test_nonsense_text_low_confidence():
    payload = _load_fixture("nonsense_text.json")
    out = assess_math_validity(payload)
    assert out["is_valid_math_problem"] is False
    assert out["confidence_percent"] < 50


def test_inline_mcq_detected():
    payload = _load_fixture("inline_mcq.json")
    out = assess_math_validity(payload)
    assert out["normalized_question"]["kind"] == "mcq"
    assert len(out["normalized_question"]["choices"] or {}) >= 4


def test_fallback_to_extracted_text_when_structured_missing():
    payload = _load_fixture("fallback_extracted_text.json")
    out = assess_math_validity(payload)
    assert "ratio" in out["normalized_question"]["stem"].lower()
    assert out["confidence_percent"] > 0

