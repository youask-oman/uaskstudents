# DB Mismatch Report

Generated: 2026-02-21

## Backup artifacts (before repair)

- `backups/db_full_20260221_154613.dump`
- `backups/db_schema_20260221_154613.sql`

Commands used:

```powershell
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d uask_db -Fc -f /tmp/db_full_20260221_154613.dump"
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d uask_db --schema-only -f /tmp/db_schema_20260221_154613.sql"
docker cp uask_postgres:/tmp/db_full_20260221_154613.dump backups/db_full_20260221_154613.dump
docker cp uask_postgres:/tmp/db_schema_20260221_154613.sql backups/db_schema_20260221_154613.sql
```

## Revision mismatch (before repair)

- DB `alembic_version`: `20260221_solve_debug_blob`
- Repo head: `20260216_drop_prompt_ck`
- `alembic current` failed with:
  - `Can't locate revision identified by '20260221_solve_debug_blob'`

Evidence files:
- `reports/db_repair/alembic_version_db.txt`
- `reports/db_repair/alembic_current_repo.txt`
- `reports/db_repair/alembic_heads_repo.txt`
- `reports/db_repair/alembic_history_verbose.txt`

## Schema diff summary (before repair)

Compared live DB (`uask_db`) vs model-contract compare DB (`uask_db_models_20260221_154703`):

- Extra table in current DB: `solvedebugblob`
- Unknown stamp row in `alembic_version`
- No missing contract columns detected
- No changed column types detected

Evidence:
- `reports/db_repair/schema_diff_summary.json`
- `reports/db_repair/schema_diff_models_20260221_154703.patch`

## Strategy used

**Strategy B** (forward repair migration + Alembic purge stamp), because:

1. DB revision was ahead with an orphan revision not present in repo.
2. Direct downgrade was impossible (`alembic` could not resolve current revision).
3. Delta was small and explicit (extra table + version drift).

Actions:

1. Added repair migration:
   - `backend/alembic/versions/20260221_restore_schema_contract.py`
   - Drops orphan `solvedebugblob` table on upgrade.
2. Repaired Alembic chain:
   - `alembic stamp --purge 20260216_drop_prompt_ck`
   - `alembic upgrade head`

## Verification after repair

Alembic:
- `alembic current`: `20260221_restore_schema_contract (head)`
- `alembic heads`: `20260221_restore_schema_contract (head)`
- DB `alembic_version`: `20260221_restore_schema_contract`

Schema:
- Post-repair diff summary confirms no drift except expected `alembic_version` bookkeeping.
- `solvedebugblob` removed.

App smoke:
- `/health` OK
- `/api/v1/solve_v3` returns `200`, provider `ollama`, `questions_count=1`

Fresh DB consistency:
- Created fresh DB, bootstrapped schema from models, stamped + upgraded Alembic to head, `current == heads`.

Evidence:
- `reports/db_repair/alembic_version_after_repair.txt`
- `reports/db_repair/alembic_current_after_repair.txt`
- `reports/db_repair/alembic_heads_after_repair.txt`
- `reports/db_repair/schema_diff_summary_after_repair.json`
- `reports/db_repair/smoke_health.json`
- `reports/db_repair/smoke_solve_v3.json`
- `reports/db_repair/fresh_verify_current.txt`
- `reports/db_repair/fresh_verify_heads.txt`

## Required Q&A

1) **What exact DB revision is currently applied (`alembic_version`)?**  
Before repair: `20260221_solve_debug_blob`  
After repair: `20260221_restore_schema_contract`

2) **What revision does the current repo expect to be at?**  
Repo head after repair migration: `20260221_restore_schema_contract`  
Prior repo head: `20260216_drop_prompt_ck`

3) **Are downgrade scripts present and tested? If not, why?**  
Downgrade path from orphan revision was not possible because repo could not resolve `20260221_solve_debug_blob`.  
Used Strategy B with explicit forward repair migration + purge stamp.

4) **What data might be impacted, and how was data loss prevented?**  
Only orphan table `solvedebugblob` was removed. Row count was `0` before drop; no business data loss.  
Full backup + schema backup taken before changes (`/backups`).

