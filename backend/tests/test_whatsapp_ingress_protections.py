from fastapi import HTTPException

from app.services.whatsapp import ingress_security


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.now = 0.0
        self.queue_len = 0

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def incrby(self, key, amount):
        self.store[key] = int(self.store.get(key, 0)) + int(amount)
        return self.store[key]

    def expire(self, key, ttl):
        return True

    def llen(self, key):
        return int(self.queue_len)

    # emulates the token bucket lua logic used in ingress_security._TOKEN_BUCKET_LUA
    def eval(self, script, numkeys, key, now, rate, burst, ttl):
        now = float(now)
        rate = float(rate)
        burst = float(burst)
        state = self.hashes.get(key, {"tokens": burst, "ts": now})
        tokens = float(state.get("tokens", burst))
        last = float(state.get("ts", now))
        elapsed = max(0.0, now - last)
        tokens = min(burst, tokens + (elapsed * rate))
        allowed = 0
        if tokens >= 1.0:
            allowed = 1
            tokens -= 1.0
        self.hashes[key] = {"tokens": tokens, "ts": now}
        return [allowed, tokens]


def test_dedup_same_message_only_once(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    assert ingress_security.enforce_dedup("m-1") is True
    assert ingress_security.enforce_dedup("m-1") is False


def test_caps_text_and_media_enforced(monkeypatch):
    monkeypatch.setenv("WHATSAPP_MAX_TEXT_CHARS", "10")
    monkeypatch.setenv("WHATSAPP_MAX_MEDIA_COUNT", "0")
    monkeypatch.setenv("WHATSAPP_MAX_METADATA_BYTES", "32")
    ingress_security.enforce_caps({"text": "abc", "hasImage": False}, b"{}")
    for payload, raw in [
        ({"text": "x" * 20}, b"{}"),
        ({"text": "ok", "hasImage": True, "upload_id": "u1"}, b"{}"),
        ({"text": "ok"}, b"0" * 40),
    ]:
        try:
            ingress_security.enforce_caps(payload, raw)
            assert False, "Expected cap rejection"
        except HTTPException as exc:
            assert exc.status_code == 413


def test_rate_limit_burst_then_throttle_then_refill(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_RL_USER_RPS", "1")
    monkeypatch.setenv("WHATSAPP_RL_USER_BURST", "2")
    monkeypatch.setenv("WHATSAPP_RL_PHONE_RPS", "1")
    monkeypatch.setenv("WHATSAPP_RL_PHONE_BURST", "2")

    t = {"v": 1000.0}
    monkeypatch.setattr(ingress_security.time, "time", lambda: t["v"])

    ingress_security.enforce_rate_limit(7, "15551230000")
    ingress_security.enforce_rate_limit(7, "15551230000")
    try:
        ingress_security.enforce_rate_limit(7, "15551230000")
        raised = False
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 429
    assert raised is True

    t["v"] += 2.2
    ingress_security.enforce_rate_limit(7, "15551230000")


def test_queue_backpressure(monkeypatch):
    fake = _FakeRedis()
    fake.queue_len = 1001
    monkeypatch.setattr(ingress_security, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_MAX_QUEUE_DEPTH", "1000")
    assert ingress_security.queue_is_overloaded() is True
