import hashlib

from app.services.message_builder import build_user_message


def test_message_builder_format():
    msg = build_user_message({"a": 1}, {"b": 2}, {"c": 3})
    assert msg.startswith("question_payload:")
    assert "\n\ncontext_payload:\n" in msg
    assert "\n\nruntime_hints:\n" in msg


def test_message_builder_stable_hash():
    payload_q = {"b": 2, "a": 1}
    payload_c = {"z": [3, 2, 1], "y": "test"}
    hints = {"mode": "solve"}
    msg1 = build_user_message(payload_q, payload_c, hints)
    msg2 = build_user_message(payload_q, payload_c, hints)
    assert hashlib.sha256(msg1.encode("utf-8")).hexdigest() == hashlib.sha256(msg2.encode("utf-8")).hexdigest()


def test_message_builder_secret_stripping():
    msg = build_user_message(
        {"problem": "test", "OPENAI_API_KEY": "sk-1234567890"},
        {"context": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----"},
        {"hint": "sk-abcdef123456"},
    )
    assert "OPENAI_API_KEY" not in msg
    assert "sk-1234567890" not in msg
    assert "sk-abcdef123456" not in msg
    assert "BEGIN PRIVATE KEY" not in msg
