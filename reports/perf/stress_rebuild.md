# Stress Test Report

Generated: 2026-02-20T05:07:23.982Z
Endpoint: GET /api/v1/public/plans
Cliff policy: p95 > 1200ms OR error rate > 2%
Result: NO CLIFF DETECTED

| Concurrency | p95 (ms) | p99 (ms) | Avg RPS | Error % | Verdict |
|---:|---:|---:|---:|---:|---|
| 1 | 11.00 | 15.00 | 168.24 | 0.00 | ok |
| 5 | 49.00 | 55.00 | 181.40 | 0.00 | ok |
| 20 | 208.00 | 344.00 | 170.67 | 0.00 | ok |
| 50 | 621.00 | 684.00 | 153.60 | 0.00 | ok |
| 75 | 755.00 | 811.00 | 165.20 | 0.00 | ok |
| 100 | 920.00 | 953.00 | 169.27 | 0.51 | ok |

