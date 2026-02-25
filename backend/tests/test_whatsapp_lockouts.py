from app.services.whatsapp import anti_abuse


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.lists = {}
        self.expiries = {}
        self.now = 1_700_000_000.0
        self.queue_len = 0

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

    def delete(self, key):
        existed = int(key in self.store)
        self.store.pop(key, None)
        self.expiries.pop(key, None)
        self.hashes.pop(key, None)
        return existed

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

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hincrby(self, key, field, amount):
        row = self.hashes.setdefault(key, {})
        row[field] = int(row.get(field, 0)) + int(amount)
        return row[field]

    def lpush(self, key, value):
        arr = self.lists.setdefault(key, [])
        arr.insert(0, value)
        return len(arr)

    def ltrim(self, key, start, end):
        arr = self.lists.setdefault(key, [])
        self.lists[key] = arr[start:end + 1]
        return True

    def lrange(self, key, start, end):
        arr = self.lists.get(key, [])
        if end < 0:
            end = len(arr) - 1
        return arr[start:end + 1]

    def scan_iter(self, match=None, count=100):
        keys = list(self.hashes.keys()) + list(self.store.keys())
        if not match:
            for key in keys:
                yield key
            return
        prefix = match.rstrip("*")
        for key in keys:
            if str(key).startswith(prefix):
                yield key

    def llen(self, key):
        return int(self.queue_len)

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


def test_lock_escalation_ladder(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_LOCK_5M_THRESHOLD", "2")
    monkeypatch.setenv("WHATSAPP_LOCK_1H_THRESHOLD", "4")
    monkeypatch.setenv("WHATSAPP_DISABLE_THRESHOLD", "5")

    out1 = anti_abuse.register_offense(10, "15550001111", "rate_limit")
    out2 = anti_abuse.register_offense(10, "15550001111", "rate_limit")
    assert out1["lock_seconds"] == 0
    assert out2["lock_seconds"] == 300
    assert anti_abuse.check_lock(10, "15550001111") is not None

    anti_abuse.register_offense(10, "15550001111", "rate_limit")
    out4 = anti_abuse.register_offense(10, "15550001111", "rate_limit")
    assert out4["lock_seconds"] == 3600

    out5 = anti_abuse.register_offense(10, "15550001111", "rate_limit")
    assert out5["disable_recommended"] is True


def test_code_bruteforce_lock_and_clear(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_MAX_INVALID_CODE_ATTEMPTS_10M", "3")

    anti_abuse.register_invalid_code_attempt("15550002222")
    anti_abuse.register_invalid_code_attempt("15550002222")
    out = anti_abuse.register_invalid_code_attempt("15550002222")
    assert out["lock_applied"] is True
    lock = anti_abuse.check_lock(None, "15550002222")
    assert lock is not None
    anti_abuse.clear_lock(user_id=None, phone="15550002222", actor="admin:test")
    assert anti_abuse.check_lock(None, "15550002222") is None


def test_queue_backpressure_and_audit(monkeypatch):
    fake = _FakeRedis()
    fake.queue_len = 150
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_MAX_OCR_QUEUE_DEPTH", "100")
    assert anti_abuse.ocr_queue_overloaded() is True

    anti_abuse.force_lock(user_id=12, phone=None, seconds=300, reason="manual", actor="admin:1")
    logs = anti_abuse.list_audit(limit=10)
    assert any(x.get("action") == "force_lock" for x in logs)
