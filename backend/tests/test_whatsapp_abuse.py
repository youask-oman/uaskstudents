from app.services.whatsapp import anti_abuse


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.lists = {}
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

    def delete(self, key):
        existed = int(key in self.store)
        self.store.pop(key, None)
        self.hashes.pop(key, None)
        self.expiries.pop(key, None)
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


def test_abuse_score_increments_and_decays(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_ABUSE_SCORE_THRESHOLD_WARN", "6")
    monkeypatch.setenv("WHATSAPP_ABUSE_SCORE_THRESHOLD_LOCK", "12")
    t = {"v": 1_700_000_000.0}
    monkeypatch.setattr(anti_abuse.time, "time", lambda: t["v"])

    anti_abuse.evaluate_abuse(22, "hello", has_media=False)
    anti_abuse.evaluate_abuse(22, "hello", has_media=False)
    result = anti_abuse.evaluate_abuse(22, "hello", has_media=False)
    assert result["score"] >= 4
    assert "repeated_identical_text" in result["reasons"] or result["warn"] is False

    t["v"] += 60 * 30
    cooled = anti_abuse.evaluate_abuse(22, "", has_media=False)
    assert cooled["score"] <= result["score"]


def test_confirmation_gate_and_circuit_flags(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(anti_abuse, "get_redis", lambda: fake)
    monkeypatch.setenv("WHATSAPP_ABUSE_SCORE_THRESHOLD_WARN", "2")
    monkeypatch.setenv("WHATSAPP_ABUSE_SCORE_THRESHOLD_LOCK", "100")

    anti_abuse.evaluate_abuse(5, "test", has_media=False)
    anti_abuse.evaluate_abuse(5, "test", has_media=False)
    third = anti_abuse.evaluate_abuse(5, "test", has_media=False)
    assert third["require_confirmation"] is True

    flags1 = anti_abuse.set_circuit_flags(disable_solve=True, disable_media=False, actor="admin:test")
    assert flags1["disable_solve"] is True
    assert flags1["disable_media"] is False
    flags2 = anti_abuse.circuit_flags()
    assert flags2["disable_solve"] is True
