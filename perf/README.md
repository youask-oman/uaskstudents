# Performance Toolkit

This folder provides reproducible performance checks without changing application behavior.

## Environment assumptions

- Backend API reachable at `PERF_BASE_URL` (default: `http://localhost:9000`).
- Optional container stats: set `PERF_DOCKER_CONTAINER=uask_orchestrator`.
- Optional auth-protected flow tests:
  - `PERF_AUTH_TOKEN` (example: `Bearer <jwt>`)
  - `PERF_SOLVE_BODY_JSON`
  - `PERF_SOLVE_BATCH_BODY_JSON`
  - `PERF_IMPORT_BODY_JSON`
- DB checks use `DATABASE_URL` (default local docker postgres URL in script).

## Suites

- CI smoke gate:
  - `npm run perf:smoke`
  - Runs load tests on smoke endpoints.
  - Compares current against `perf/perf_baseline.json`.
  - Fails if:
    - p95 latency regression > 15%
    - RPS drop > 10%
    - error rate increases (absolute)
  - Runs frontend bundle budget check.

- Local full:
  - `npm run perf:full`
  - Runs:
    - full endpoint load matrix
    - stress runner (find cliff)
    - soak runner (latency drift)
    - DB checks + markdown report
    - runtime safety static audit report
    - container sanity report
    - bundle budget check

## Commands

1. Start services:
   - `docker compose -f docker-compose.yml up -d postgres redis orchestrator`
2. Run CI smoke locally:
   - `npm run perf:smoke`
3. Run local full suite:
   - `npm run perf:full`

## Output Files

- `perf/perf_baseline.json`
- `reports/perf_baseline.md`
- `reports/perf_regression.md`
- `reports/perf/perf_regression.json`
- `reports/perf/stress.md`
- `reports/perf/soak.md`
- `reports/db_perf.md`
- `reports/runtime_safety.md`
- `reports/container_sanity.md`
- `reports/perf_bundle_budget.json`

## Optional Profiles

`profiles/` is reserved for local CPU profiling artifacts.

Example (`py-spy` installed):
`py-spy record -o profiles/solve.svg --pid <uvicorn_pid> --duration 60`

If profiling tooling is unavailable in environment, document as not measured.