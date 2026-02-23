import json

from app.services.solve.batch_tier_runtime import (
    FREE_BATCH_SCHEMA_NAME,
    _build_free_batch_prompt_variables,
    _load_free_batch_schema_wrapper,
    _questions_json_compact,
)


def test_questions_json_compact_unicode_preserved():
    questions = [{"question_id": "q1", "question_text": "حل المعادلة x+1=2"}]
    got = _questions_json_compact(questions)
    assert got == json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
    assert "\\u" not in got
    assert ": " not in got
    assert ", " not in got


def test_free_prompt_variables_include_required_bindings():
    questions = [{"question_id": "q1", "question_text": "Solve: 2x+3=11"}]
    vars_map = _build_free_batch_prompt_variables(
        runtime_request_id="req-1",
        runtime_attempt_id="att-1",
        runtime_mode="SOLVE",
        runtime_graph="OFF",
        runtime_domain="reals",
        runtime_lang="English",
        normalized_questions=questions,
    )
    required = {
        "REQUEST_ID",
        "ATTEMPT_ID",
        "TIER",
        "MAX_QUESTIONS",
        "MODE",
        "GRAPH_MODE",
        "DOMAIN_MODE",
        "PREFERRED_RESPONSE_LANGUAGE",
        "QUESTIONS_JSON",
    }
    assert required.issubset(set(vars_map.keys()))
    assert vars_map["TIER"] == "FREE"
    assert vars_map["QUESTIONS_JSON"] == json.dumps(questions, ensure_ascii=False, separators=(",", ":"))


def test_free_schema_wrapper_loaded_from_repo():
    wrapper = _load_free_batch_schema_wrapper()
    assert wrapper.get("type") == "json_schema"
    assert wrapper.get("strict") is True
    assert wrapper.get("name") == FREE_BATCH_SCHEMA_NAME
    assert isinstance(wrapper.get("schema"), dict)
    assert wrapper["schema"].get("type") == "object"

