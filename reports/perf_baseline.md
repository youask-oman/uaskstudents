# Performance Baseline

Generated: 2026-02-20T03:32:28.913Z
Suite: perf-smoke
Base URL: http://localhost:9000

## Critical Flows
- Solve endpoints: /api/v1/solve, /api/v1/solve/batch (configured as optional; require auth/payload env)
- Auth/session endpoints: /api/v1/login and /api/v1/history (optional; require auth env)
- History/profile endpoints: /api/v1/history, /api/v1/user/profile (optional; require auth env)
- Upload/import endpoints: /api/v1/uploads, /api/v1/import (optional; require multipart/auth env)

## Smoke Results
| Endpoint | Concurrency | p50 (ms) | p95 (ms) | p99 (ms) | Avg RPS | Error % | Avg CPU % | Max Mem (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| health | 1 | 2 | 2004 | 2007 | 21.5 | 0.00 | 0.95 | 675.10 |
| health | 5 | 11 | 2009 | 2014 | 32.25 | 0.00 | 1.30 | 667.10 |
| health | 20 | 69 | 2009 | 2010 | 45 | 0.00 | 1.22 | 664.50 |
| health | 50 | 2001 | 2014 | 2016 | 71.88 | 0.00 | 1.98 | 674.80 |
| public_plans | 1 | 5 | 2005 | 2010 | 11.19 | 0.00 | 2.02 | 684.70 |
| public_plans | 5 | 25 | 2008 | 2013 | 18.67 | 0.00 | 1.33 | 663.50 |
| public_plans | 20 | 127 | 150 | 150 | 5 | 50.00 | 0.00 | 682.70 |
| public_plans | 50 | 0 | 0 | 0 | 0 | 100.00 | 0.00 | 708.40 |
| legal_terms | 1 | 0 | 0 | 0 | 0 | 100.00 | 0.00 | 734.20 |
| legal_terms | 5 | 0 | 0 | 0 | 0 | 100.00 | 0.00 | 759.20 |
| legal_terms | 20 | 0 | 0 | 0 | 0 | 100.00 | 2.33 | 784.60 |
| legal_terms | 50 | 0 | 0 | 0 | 0 | 100.00 | 4.61 | 799.10 |

## Skipped Endpoints
- solve_batch_optional: Missing required env: PERF_AUTH_TOKEN, PERF_SOLVE_BATCH_BODY_JSON
- history_optional: Missing required env: PERF_AUTH_TOKEN
- profile_optional: Missing required env: PERF_AUTH_TOKEN

## Notes
- Baseline artifact is persisted at perf/perf_baseline.json.
- CI gate compares current run against this baseline with threshold checks.
