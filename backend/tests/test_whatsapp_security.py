import hmac
import os
from hashlib import sha256

from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from app.services.whatsapp import ingress_security


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def setex(self, key, ex, value):
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def incrby(self, key, amount):
        self.store[key] = int(self.store.get(key, 0)) + int(amount)
        return self.store[key]

    def expire(self, key, ttl):
        return True


def _sign(secret: str, ts: str, nonce: str, raw: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), f"{ts}.{nonce}.".encode("utf-8") + raw, sha256).hexdigest()
    return f"sha256={digest}"


def _build_app():
    app = FastAPI()

    @app.post("/signed")
    async def signed_endpoint(request: Request):
        await ingress_security.verify_request_signature(request)
        return {"ok": True}

    return app


def test_signature_valid_accepted(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_SIGNING_SECRET", "sig-secret")
    monkeypatch.setenv("WHATSAPP_SIGNATURE_MAX_DRIFT_SECONDS", "300")
    monkeypatch.setattr(ingress_security.time, "time", lambda: 1_700_000_000)

    app = _build_app()
    client = TestClient(app)
    raw = b'{"from":"123@s.whatsapp.net","text":"x+1=2","message_id":"m1"}'
    ts = "1700000000"
    nonce = "n-1"
    sig = _sign("sig-secret", ts, nonce, raw)
    res = client.post(
        "/signed",
        data=raw,
        headers={
            "Content-Type": "application/json",
            ingress_security.SIG_TS_HEADER: ts,
            ingress_security.SIG_NONCE_HEADER: nonce,
            ingress_security.SIG_HEADER: sig,
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_signature_invalid_rejected(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_SIGNING_SECRET", "sig-secret")
    monkeypatch.setattr(ingress_security.time, "time", lambda: 1_700_000_000)
    app = _build_app()
    client = TestClient(app)
    raw = b'{"x":1}'
    res = client.post(
        "/signed",
        data=raw,
        headers={
            "Content-Type": "application/json",
            ingress_security.SIG_TS_HEADER: "1700000000",
            ingress_security.SIG_NONCE_HEADER: "n-2",
            ingress_security.SIG_HEADER: "sha256=bad",
        },
    )
    assert res.status_code == 401


def test_signature_missing_rejected(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_SIGNING_SECRET", "sig-secret")
    app = _build_app()
    client = TestClient(app)
    res = client.post("/signed", json={"x": 1})
    assert res.status_code == 401


def test_signature_replay_nonce_rejected(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_SIGNING_SECRET", "sig-secret")
    monkeypatch.setattr(ingress_security.time, "time", lambda: 1_700_000_000)
    app = _build_app()
    client = TestClient(app)
    raw = b'{"x":1}'
    ts = "1700000000"
    nonce = "same-nonce"
    sig = _sign("sig-secret", ts, nonce, raw)
    h = {
        "Content-Type": "application/json",
        ingress_security.SIG_TS_HEADER: ts,
        ingress_security.SIG_NONCE_HEADER: nonce,
        ingress_security.SIG_HEADER: sig,
    }
    assert client.post("/signed", data=raw, headers=h).status_code == 200
    assert client.post("/signed", data=raw, headers=h).status_code == 409


def test_signature_timestamp_drift_rejected(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_SIGNING_SECRET", "sig-secret")
    monkeypatch.setenv("WHATSAPP_SIGNATURE_MAX_DRIFT_SECONDS", "300")
    monkeypatch.setattr(ingress_security.time, "time", lambda: 1_700_000_000)
    app = _build_app()
    client = TestClient(app)
    raw = b'{"x":1}'
    ts = "1699999000"
    nonce = "n-drift"
    sig = _sign("sig-secret", ts, nonce, raw)
    res = client.post(
        "/signed",
        data=raw,
        headers={
            "Content-Type": "application/json",
            ingress_security.SIG_TS_HEADER: ts,
            ingress_security.SIG_NONCE_HEADER: nonce,
            ingress_security.SIG_HEADER: sig,
        },
    )
    assert res.status_code == 401
