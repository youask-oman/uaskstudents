import os
from types import SimpleNamespace

import app.services.whatsapp.whatsapp_send as ws


def test_send_whatsapp_image_posts_payload(monkeypatch):
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        calls["headers"] = headers
        calls["timeout"] = timeout
        return SimpleNamespace(status_code=200)

    def fake_log(event):
        calls["log"] = event

    monkeypatch.setenv("WHATSAPP_INTERNAL_PORT", "9999")
    monkeypatch.setenv("WHATSAPP_INTERNAL_KEY", "secret")
    monkeypatch.setenv("WHATSAPP_INTERNAL_SEND_MEDIA_URL", "http://orchestrator:9999/send-media")
    monkeypatch.setattr(ws.requests, "post", fake_post)
    monkeypatch.setattr(ws, "log_whatsapp_event", fake_log)

    ok = ws.send_whatsapp_image("123@s.whatsapp.net", "abc123", content_type="image/webp", caption="cap")
    assert ok is True
    assert calls["url"] == "http://orchestrator:9999/send-media"
    assert calls["json"] == {
        "to": "123@s.whatsapp.net",
        "bytesBase64": "abc123",
        "contentType": "image/webp",
        "caption": "cap",
    }
    assert calls["headers"]["X-UASK-INTERNAL-KEY"] == "secret"
    assert calls["timeout"] == 10
