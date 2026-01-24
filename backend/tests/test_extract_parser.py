import json
import pytest

from app.api import _extract_openai_text, _parse_json_response


class DummyResponse:
    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


def test_extract_openai_text_from_output_text():
    resp = DummyResponse(output_text='  {"foo":1}  ')
    assert _extract_openai_text(resp) == '{"foo":1}'


def test_extract_openai_text_from_output_items():
    inner = DummyResponse(content=[{"text": ' {"bar":2} '}])
    resp = DummyResponse(output=[inner])
    assert _extract_openai_text(resp) == '{"bar":2}'


def test_extract_openai_text_from_chat_choices():
    resp = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "output_text", "text": '{"chat":3}'}
                    ]
                }
            }
        ]
    }
    assert _extract_openai_text(resp) == '{"chat":3}'


def test_parse_json_response_plain_json():
    payload = '{"foo": 1}'
    assert _parse_json_response(payload) == {"foo": 1}


def test_parse_json_response_with_prefix_and_code_fence():
    payload = 'Some text ```json\n{"foo": 4}\n```'
    assert _parse_json_response(payload) == {"foo": 4}


def test_parse_json_response_empty_string():
    with pytest.raises(ValueError, match='Empty content received from extract model'):
        _parse_json_response('   \n  ')


def test_extract_schema_validation_fallback():
    from app.api import _validate_extract_payload, INVALID_EXTRACT_PAYLOAD
    payload = {"ok": True}
    assert _validate_extract_payload(payload) == INVALID_EXTRACT_PAYLOAD


def test_extract_responses_message_text_multi_block():
    from app.api import _extract_responses_message_text

    class Part:
        def __init__(self, text=None):
            self.text = text

    class Item:
        def __init__(self, content, type_value="message"):
            self.content = content
            self.type = type_value

    resp = type("Resp", (), {
        "output": [
            Item([Part("{\"ok\":true,\"questions\":"), Part("[]}")])
        ]
    })()
    assert _extract_responses_message_text(resp) == '{"ok":true,"questions":[]}'


def test_extract_responses_message_text_ignores_non_text():
    from app.api import _extract_responses_message_text

    class Part:
        def __init__(self, text=None):
            self.text = text

    class Item:
        def __init__(self, content, type_value="message"):
            self.content = content
            self.type = type_value

    resp = type("Resp", (), {
        "output": [
            Item([Part(None), {"type": "output_text", "text": "{\"ok\":false}"}])
        ]
    })()
    assert _extract_responses_message_text(resp) == '{"ok":false}'


def test_extract_responses_message_text_no_message():
    from app.api import _extract_responses_message_text

    class Item:
        def __init__(self, content, type_value="reasoning"):
            self.content = content
            self.type = type_value

    resp = type("Resp", (), {"output": [Item([])]})()
    assert _extract_responses_message_text(resp) == ""


def test_ratios_to_pixels_mapping():
    from app.api import _ratios_to_pixels
    crop = {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.25}
    x, y, w, h = _ratios_to_pixels(crop, 1000, 800)
    assert (x, y, w, h) == (100, 160, 500, 200)


def test_normalize_crop_ratios_from_pixels():
    from app.api import _normalize_crop_ratios
    ratios = _normalize_crop_ratios(50, 100, 200, 300, 500, 1000, 900, 1800)
    assert ratios == {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.3}


def test_should_cache_extract_result_false():
    from app.api import _should_cache_extract_result
    result = {"ok": False, "error": "Could not read text", "questions": []}
    assert _should_cache_extract_result(result) is False
