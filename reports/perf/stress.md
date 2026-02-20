# Stress Test Report

Generated: 2026-02-20T04:46:43.600Z
Endpoint: GET /api/v1/public/plans
Cliff policy: p95 > 1200ms OR error rate > 2%
Result: NO CLIFF DETECTED

| Concurrency | p95 (ms) | p99 (ms) | Avg RPS | Error % | Verdict |
|---:|---:|---:|---:|---:|---|
| 1 | 6.00 | 6.00 | 187.00 | 0.00 | ok |
| 5 | 30.00 | 31.00 | 191.87 | 0.00 | ok |
| 20 | 111.00 | 297.00 | 198.70 | 0.00 | ok |
| 50 | 456.00 | 459.00 | 195.04 | 0.00 | ok |
| 75 | 650.00 | 663.00 | 172.50 | 0.31 | ok |
| 100 | 789.00 | 817.00 | 173.34 | 0.76 | ok |

