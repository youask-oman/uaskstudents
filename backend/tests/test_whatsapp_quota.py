from app.services.whatsapp import anti_abuse


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.expiries = {}
        self.now = 1_700_000_000.0

    def _expired(self, key):
        exp = self.expiries.get(key)
        if exp is not None and self.now >= exp:
            self.store.pop(key, None)
            self.hashes.pop(key, None)
            self.expiries.pop(key, None)
            return True
        return False

    def get(self, key):
        self._expired(key)
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = str(value)
        return True

    def setex(self, key, ex, value):
        self.store[key] = str(value)
        self.expiries[key] = self.now + int(ex)
        return True

    def incrby(self, key, amount):
        self._expired(key)
        val = int(self.store.get(key, 0)) + int(amount)
        self.store[key] = str(val)
        return val

    def expire(self, key, ex):
        self.expiries[key] = self.now + int(ex)
        return True

    def ttl(self, key):
        self._expired(key)
        exp = self.expiries.get(key)
        if exp is None:
            return -1
        left = int(exp - self.now)
        return left if left > 0 else -2

    def eval(self, script, numkeys, *argv):
        if int(numkeys) == 1:
            key, now, rate, burst, _ttl = argv
            now = float(now)
            rate = float(rate)
            burst = float(burst)
            state = self.hashes.get(key, {"tokens": burst, "ts": now})
            tokens = float(state.get("tokens", burst))
            last = float(state.get("ts", now))
            elapsed = max(0.0, now - last)
            tokens = min(burst, tokens + (elapsed * rate))
            allowed = 0
            retry = 0
            if tokens >= 1:
                allowed = 1
                tokens -= 1
            elif rate > 0:
                retry = max(1, int((1 - tokens + rate - 1e-9) / rate))
            self.hashes[key] = {"tokens": tokens, "ts": now}
            return [allowed, tokens, retry]
        score_key, ts_key, now, add_points, decay_per_minute, _ttl = argv
        now = float(now)
        add_points = float(add_points)
        decay_per_minute = float(decay_per_minute)
        score = float(self.store.get(score_key, "0"))
        last = float(self.store.get(ts_key, str(now)))
        elapsed = max(0.0, now - last)
        score = max(0.0, score - ((elapsed / 60.0) * decay_per_minute))
        score += add_points
        self.store[score_key] = str(score)
        self.store[ts_key] = str(now)
        return score


def test_solve_quota_daily_and_burst(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_QUOTA_SOLVES_PER_DAY", "3")
    monkeypatch.setenv("WHATSAPP_QUOTA_SOLVES_PER_10M", "2")

    ok1, _ = anti_abuse.check_and_consume_quota(7, "solve")
    ok2, _ = anti_abuse.check_and_consume_quota(7, "solve")
    ok3, retry3 = anti_abuse.check_and_consume_quota(7, "solve")
    assert ok1 is True
    assert ok2 is True
    assert ok3 is False
    assert int(retry3) > 0


def test_quota_resets_by_day_key(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_QUOTA_SOLVES_PER_DAY", "1")
    monkeypatch.setenv("WHATSAPP_QUOTA_SOLVES_PER_10M", "100")
    monkeypatch.setattr(anti_abuse, "_utc_day_key", lambda now=None: "20260101")
    monkeypatch.setattr(anti_abuse, "_seconds_until_utc_midnight", lambda now=None: 3600)

    ok1, _ = anti_abuse.check_and_consume_quota(9, "solve")
    ok2, _ = anti_abuse.check_and_consume_quota(9, "solve")
    assert ok1 is True
    assert ok2 is False

    monkeypatch.setattr(anti_abuse, "_utc_day_key", lambda now=None: "20260102")
    ok3, _ = anti_abuse.check_and_consume_quota(9, "solve")
    assert ok3 is True
