import json

from app.services.solve.batch_tier_runtime import (
    FREE_BATCH_SCHEMA_NAME,
    _adapt_min_final_payload_to_v2,
    _build_free_batch_prompt_variables,
    _load_free_batch_schema_wrapper,
    _normalize_provider_batch_payload,
    _post_assertions,
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


def test_normalize_provider_payload_strips_unknown_keys_when_schema_is_strict():
    payload = {
        "schema_name": "youask_math_openai_min_final_batch_v1",
        "schema_version": "v1",
        "request_id": "",
        "attempt_id": "",
        "tier": "",
        "mode": "",
        "domain_mode": "reals",
        "preferred_response_language": "en",
        "items": [
            {
                "question_id": "q1",
                "question_text": "",
                "status": "ok",
                "answer_text": "2",
                "answer_latex": "2",
                "refusal_reason": None,
                "safe_next_step": None,
                "error_message": None,
                "unexpected_item_key": "drop-me",
            }
        ],
        "unexpected_root_key": "drop-me-too",
    }
    normalized_questions = [{"question_id": "q1", "question_text": "Solve x+1=2"}]
    normalized = _normalize_provider_batch_payload(
        payload,
        runtime_request_id="req-123",
        runtime_attempt_id="att-456",
        external_tier="FINAL",
        runtime_mode="SOLVE",
        runtime_domain="reals",
        runtime_lang="en",
        normalized_questions=normalized_questions,
        allowed_root_keys={
            "schema_name",
            "schema_version",
            "request_id",
            "attempt_id",
            "tier",
            "mode",
            "domain_mode",
            "preferred_response_language",
            "items",
        },
        allow_item_question_text=True,
        allowed_item_keys={
            "question_id",
            "question_text",
            "status",
            "answer_text",
            "answer_latex",
            "refusal_reason",
            "safe_next_step",
            "error_message",
        },
        prune_unknown_root_keys=True,
        prune_unknown_item_keys=True,
    )

    assert normalized["request_id"] == "req-123"
    assert normalized["attempt_id"] == "att-456"
    assert normalized["tier"] == "FINAL"
    assert normalized["mode"] == "SOLVE"
    assert normalized["items"][0]["question_text"] == "Solve x+1=2"
    assert "unexpected_root_key" not in normalized
    assert "unexpected_item_key" not in normalized["items"][0]


def test_adapt_min_final_payload_to_v2_normalizes_general_mode():
    adapted = _adapt_min_final_payload_to_v2(
        {
            "items": [
                {
                    "question_id": "q1",
                    "question_text": "Find x",
                    "status": "ok",
                    "answer_text": "2",
                    "answer_latex": "2",
                    "refusal_reason": None,
                    "safe_next_step": None,
                    "error_message": None,
                }
            ]
        },
        runtime_mode="GENERAL",
        runtime_lang="en",
        external_tier="FINAL",
        normalized_questions=[{"question_id": "q1", "question_text": "Find x"}],
    )
    assert adapted["items"][0]["mode"] == "SOLVE"


def test_post_assertions_accepts_min_final_schema_without_quality_confidence():
    payload = {
        "schema_name": "youask_math_openai_min_final_batch_v1",
        "schema_version": "v1",
        "request_id": "3372085f-27ab-424c-ab57-6ec99a79708b",
        "attempt_id": "60718279-c3bd-44f4-8acb-c6cb3e29f2fa",
        "tier": "FINAL",
        "mode": "SOLVE",
        "domain_mode": "reals",
        "preferred_response_language": "en",
        "items": [
            {
                "question_id": "q1",
                "question_text": "Q1",
                "status": "ok",
                "answer_text": "AB:BC = sqrt(3):1",
                "answer_latex": "\\sqrt{3}:1",
                "refusal_reason": None,
                "safe_next_step": None,
                "error_message": None,
            }
        ],
    }
    schema_body = {
        "type": "object",
        "properties": {
            "schema_name": {"type": "string"},
            "schema_version": {"type": "string"},
            "request_id": {"type": "string"},
            "attempt_id": {"type": "string"},
            "tier": {"type": "string"},
            "mode": {"type": "string"},
            "domain_mode": {"type": "string"},
            "preferred_response_language": {"type": "string"},
            "items": {"type": "array", "items": {"$ref": "#/$defs/SolveItem"}},
        },
        "$defs": {
            "SolveItem": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "question_text": {"type": "string"},
                    "status": {"type": "string"},
                    "answer_text": {"type": ["string", "null"]},
                    "answer_latex": {"type": ["string", "null"]},
                    "refusal_reason": {"type": ["string", "null"]},
                    "safe_next_step": {"type": ["string", "null"]},
                    "error_message": {"type": ["string", "null"]},
                },
            }
        },
    }
    questions = [{"question_id": "q1", "question_text": "Q1"}]

    _post_assertions(payload, schema_body=schema_body, questions=questions, tier="FINAL")
