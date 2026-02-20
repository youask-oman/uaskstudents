# Soak Test Report

Generated: 2026-02-20T04:48:44.285Z
Endpoint: GET /api/v1/public/plans
Total duration: 120s
Window duration: 60s
Connections: 20

| Window | p95 (ms) | p99 (ms) | Avg RPS | Error % |
|---:|---:|---:|---:|---:|
| 1 | 113.00 | 298.00 | 198.72 | 0.00 |
| 2 | 117.00 | 301.00 | 197.20 | 0.00 |

## Drift
- p95 drift: 3.54%
- error drift: 0.00 percentage points
- memory growth tracking: Not directly measured in soak runner; use PERF_DOCKER_CONTAINER in load_runner outputs for memory sample trends.
