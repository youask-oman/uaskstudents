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
