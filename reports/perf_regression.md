# Performance Regression Report

Generated: 2026-02-20T05:10:49.504Z
Baseline: perf/perf_baseline.json
Current: reports/perf/perf_current.json

## Thresholds
- p95 latency regression: fail if > +15%
- RPS regression: fail if drop > 10%
- Error rate: fail on increase > 0 absolute % points

Overall gate: **FAIL**

| Endpoint | C | p95 base | p95 curr | p95 d% | RPS base | RPS curr | RPS d% | Err base % | Err curr % | Gate | Violations | 
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| health | 1 | 2004.00 | 2004.00 | 0.00 | 21.50 | 7.82 | -63.63 | 0.00 | 0.00 | FAIL | rps -63.63% < -10.00% |
| health | 20 | 2009.00 | 2005.00 | -0.20 | 45.00 | 25.00 | -44.44 | 0.00 | 0.00 | FAIL | rps -44.44% < -10.00% |
| health | 5 | 2009.00 | 2007.00 | -0.10 | 32.25 | 12.19 | -62.20 | 0.00 | 0.00 | FAIL | rps -62.20% < -10.00% |
| health | 50 | 2014.00 | 2349.00 | 16.63 | 71.88 | 56.25 | -21.74 | 0.00 | 0.00 | FAIL | p95 +16.63% > +15.00%; rps -21.74% < -10.00% |
| legal_terms | 1 | 0.00 | 2006.00 | n/a | 0.00 | 7.13 | n/a | 100.00 | 50.00 | PASS | - |
| legal_terms | 20 | 0.00 | 2006.00 | n/a | 0.00 | 30.13 | n/a | 100.00 | 50.00 | PASS | - |
| legal_terms | 5 | 0.00 | 2010.00 | n/a | 0.00 | 16.69 | n/a | 100.00 | 50.00 | PASS | - |
| legal_terms | 50 | 0.00 | 2009.00 | n/a | 0.00 | 58.19 | n/a | 100.00 | 50.00 | PASS | - |
| public_plans | 1 | 2005.00 | 2237.00 | 11.57 | 11.19 | 1.07 | -90.44 | 0.00 | 0.00 | FAIL | rps -90.44% < -10.00% |
| public_plans | 20 | 150.00 | 2007.00 | 1238.00 | 5.00 | 30.00 | 500.00 | 50.00 | 0.00 | FAIL | p95 +1238.00% > +15.00% |
| public_plans | 5 | 2008.00 | 2007.00 | -0.05 | 18.67 | 5.32 | -71.51 | 0.00 | 0.00 | FAIL | rps -71.51% < -10.00% |
| public_plans | 50 | 0.00 | 2215.00 | n/a | 0.00 | 59.38 | n/a | 100.00 | 0.00 | PASS | - |

## Skipped Endpoints
- Baseline:
  - solve_batch_optional: Missing required env: PERF_AUTH_TOKEN, PERF_SOLVE_BATCH_BODY_JSON
  - history_optional: Missing required env: PERF_AUTH_TOKEN
  - profile_optional: Missing required env: PERF_AUTH_TOKEN
- Current:
  - solve_batch_optional: Missing required env: PERF_AUTH_TOKEN, PERF_SOLVE_BATCH_BODY_JSON
  - history_optional: Missing required env: PERF_AUTH_TOKEN
  - profile_optional: Missing required env: PERF_AUTH_TOKEN

