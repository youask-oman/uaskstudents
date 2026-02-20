# Container Sanity Report

Generated: 2026-02-20T04:48:44.839Z

## Compose Resource Limits
- No explicit CPU/memory/ulimits limits set in docker-compose.yml.

## Concurrency Controls
- --concurrency=${WORKER_CONCURRENCY:-4}
- --concurrency=${WHATSAPP_WORKER_CONCURRENCY:-2} -Q whatsapp

## Runtime Hardening Flags
- max-size: "10m"
- max-file: "3"
- read_only: false
- tmpfs:
- no-new-privileges:true
- max-size: "4m"
- max-file: "2"
- read_only: false
- tmpfs:
- no-new-privileges:true
- max-size: "4m"
- max-file: "2"
- read_only: true
- tmpfs:
- no-new-privileges:true

## DB Pool Notes
- pool
- pool
- pool
- pool
- create_engine(
- Session(
- Session(

## Findings
- Risk: missing explicit container CPU/memory/ulimit boundaries can cause noisy-neighbor impact and OOM under load.
- Positive: worker concurrency is parameterized via env for queue consumers.
- Positive: some services use tmpfs and no-new-privileges; log rotation options are present.
- Risk: DB pool sizing is not explicitly tuned in compose/env and should be load-tested per deployment size.

## Dev Override Review
- docker-compose.dev.yml runs orchestrator/worker as root and with read_only=false for convenience.
- Keep dev override out of production deploy paths.
