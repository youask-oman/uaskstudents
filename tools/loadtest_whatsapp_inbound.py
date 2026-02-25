#!/usr/bin/env python
import argparse
import asyncio
import hmac
import json
import statistics
import time
import uuid
from hashlib import sha256

import httpx


def sign(secret: str, ts: int, nonce: str, raw: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), f"{ts}.{nonce}.".encode("utf-8") + raw, sha256).hexdigest()
    return f"sha256={digest}"


async def one_call(
    client: httpx.AsyncClient,
    url: str,
    signing_secret: str,
    idx: int,
) -> tuple[float, int, dict]:
    payload = {
        "from": f"1555000{idx:04d}@s.whatsapp.net",
        "text": "solve x+1=2",
        "hasImage": False,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message_id": f"load-{idx}-{uuid.uuid4().hex[:10]}",
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ts = int(time.time())
    nonce = str(uuid.uuid4())
    request_id = f"load-{idx}-{uuid.uuid4().hex[:8]}"
    headers = {
        "Content-Type": "application/json",
        "X-YouAsk-Timestamp": str(ts),
        "X-YouAsk-Nonce": nonce,
        "X-YouAsk-Signature": sign(signing_secret, ts, nonce, raw),
        "X-Request-Id": request_id,
    }

    t0 = time.perf_counter()
    resp = await client.post(url, content=raw, headers=headers)
    latency_ms = (time.perf_counter() - t0) * 1000
    data = {}
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    return latency_ms, resp.status_code, data


async def run(url: str, signing_secret: str, total: int, concurrency: int):
    limits = httpx.Limits(max_connections=max(concurrency * 2, 200), max_keepalive_connections=max(concurrency, 100))
    timeout = httpx.Timeout(15.0, connect=5.0)
    sem = asyncio.Semaphore(concurrency)
    latencies = []
    status_counts = {}
    ack_count = 0

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        async def wrapped(i: int):
            async with sem:
                latency_ms, status, data = await one_call(client, url, signing_secret, i)
                latencies.append(latency_ms)
                status_counts[status] = status_counts.get(status, 0) + 1
                if isinstance(data, dict) and isinstance(data.get("reply"), str):
                    ack_count_nonlocal[0] += 1

        ack_count_nonlocal = [0]
        tasks = [asyncio.create_task(wrapped(i)) for i in range(total)]
        await asyncio.gather(*tasks)
        ack_count = ack_count_nonlocal[0]

    if not latencies:
        raise RuntimeError("No requests completed")
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    print(json.dumps(
        {
            "total_requests": total,
            "concurrency": concurrency,
            "status_counts": status_counts,
            "ack_count": ack_count,
            "latency_ms": {
                "min": round(min(latencies), 2),
                "avg": round(sum(latencies) / len(latencies), 2),
                "p95": round(p95, 2),
                "max": round(max(latencies), 2),
            },
        },
        indent=2,
    ))


def main():
    parser = argparse.ArgumentParser(description="Local WhatsApp inbound load test (signed requests)")
    parser.add_argument("--url", default="http://127.0.0.1:9000/api/v1/whatsapp/message")
    parser.add_argument("--secret", required=True, help="WHATSAPP_SIGNING_SECRET")
    parser.add_argument("--total", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    args = parser.parse_args()

    asyncio.run(run(args.url, args.secret, args.total, args.concurrency))


if __name__ == "__main__":
    main()
