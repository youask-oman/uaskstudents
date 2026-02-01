import asyncio
import statistics
import time

import httpx


API_URL = "http://127.0.0.1:8000/api/v1/admin/prompt-registry/test"


async def one_call(client: httpx.AsyncClient, i: int) -> float:
    payload = {
        "tier": "FREE",
        "mode": "SOLVE",
        "question_payload": {"problem": f"Solve x + {i} = {i+3}"},
        "context_payload": {"locale": "en-US"},
        "runtime_hints": {"requested_mode": "minimal"},
    }
    start = time.perf_counter()
    resp = await client.post(API_URL, json=payload, timeout=60)
    resp.raise_for_status()
    _ = resp.json()
    return (time.perf_counter() - start) * 1000


async def main(concurrency: int = 10):
    async with httpx.AsyncClient() as client:
        tasks = [one_call(client, i) for i in range(concurrency)]
        latencies = await asyncio.gather(*tasks)

    print(f"calls={len(latencies)}")
    print(f"latency_ms_min={min(latencies):.2f}")
    print(f"latency_ms_p50={statistics.median(latencies):.2f}")
    print(f"latency_ms_max={max(latencies):.2f}")
    print(f"latency_ms_avg={statistics.mean(latencies):.2f}")


if __name__ == "__main__":
    asyncio.run(main(10))
