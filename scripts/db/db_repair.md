# DB Repair Runbook (Schema-Contract Restore)

This runbook restores Postgres schema compatibility with the **current checked-out codebase** after code rollback + DB-forward drift.

## Preconditions

- Docker Compose project root: `e:\uaskstudents`
- Services: `orchestrator`, `postgres`
- DB: `uask_db`

## 1) Freeze + Backup (mandatory)

```powershell
$ts=Get-Date -Format 'yyyyMMdd_HHmmss'
New-Item -ItemType Directory -Path backups -Force | Out-Null
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d uask_db -Fc -f /tmp/db_full_$ts.dump"
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d uask_db --schema-only -f /tmp/db_schema_$ts.sql"
docker cp uask_postgres:/tmp/db_full_$ts.dump backups/db_full_$ts.dump
docker cp uask_postgres:/tmp/db_schema_$ts.sql backups/db_schema_$ts.sql
```

## 2) Detect mismatch

```powershell
docker exec uask_postgres psql -U uask_user -d uask_db -c "SELECT version_num FROM alembic_version;"
docker exec uask_orchestrator sh -lc "cd /app && alembic current"
docker exec uask_orchestrator sh -lc "cd /app && alembic heads"
docker exec uask_orchestrator sh -lc "cd /app && alembic history --verbose"
```

If DB version is unknown to current repo (example: `Can't locate revision ...`), continue to step 3.

## 3) Strategy B (forward repair migration + purge stamp)

Migration file:
- `backend/alembic/versions/20260221_restore_schema_contract.py`

Apply repair:

```powershell
docker exec uask_orchestrator sh -lc "cd /app && alembic stamp --purge 20260216_drop_prompt_ck"
docker exec uask_orchestrator sh -lc "cd /app && alembic upgrade head"
```

Verify:

```powershell
docker exec uask_postgres psql -U uask_user -d uask_db -c "SELECT version_num FROM alembic_version;"
docker exec uask_orchestrator sh -lc "cd /app && alembic current"
docker exec uask_orchestrator sh -lc "cd /app && alembic heads"
```

## 4) Schema diff validation

Create model-contract compare DB, bootstrap schema from current models, and diff:

```powershell
$cmp='uask_db_models_'+(Get-Date -Format 'yyyyMMdd_HHmmss')
docker exec uask_postgres psql -U uask_user -d postgres -c "CREATE DATABASE $cmp;"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$cmp python - <<'PY'
from app.models import SQLModel
from app.database import engine
SQLModel.metadata.create_all(engine)
print('created')
PY"
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d uask_db --schema-only -f /tmp/current_schema.sql"
docker exec uask_postgres sh -lc "pg_dump -U uask_user -d $cmp --schema-only -f /tmp/expected_schema.sql"
docker cp uask_postgres:/tmp/current_schema.sql reports/db_repair/current_schema_after_repair.sql
docker cp uask_postgres:/tmp/expected_schema.sql reports/db_repair/expected_models_schema.sql
git --no-pager diff --no-index -- reports/db_repair/expected_models_schema.sql reports/db_repair/current_schema_after_repair.sql
```

## 5) Smoke verification

```powershell
Invoke-RestMethod -Uri 'http://localhost:9000/health' -Method Get
python - <<'PY'
import requests
payload={"confirmed_text":"Solve x+1=2","tier":"SHORT_STEPS","requested_mode":"minimal","graph_mode":"off"}
r=requests.post('http://localhost:9000/api/v1/solve_v3?user_id=2',json=payload,timeout=180)
print(r.status_code)
print((r.json().get("telemetry") or {}).get("provider"))
print((r.json().get("telemetry") or {}).get("questions_count"))
PY
```

## 6) Fresh DB consistency check

```powershell
$fresh='uask_db_fresh_verify_'+(Get-Date -Format 'yyyyMMdd_HHmmss')
docker exec uask_postgres psql -U uask_user -d postgres -c "CREATE DATABASE $fresh;"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$fresh python - <<'PY'
from app.models import SQLModel
from app.database import engine
SQLModel.metadata.create_all(engine)
print('bootstrap_create_all_done')
PY"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$fresh alembic stamp 20260221_restore_schema_contract"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$fresh alembic upgrade head"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$fresh alembic current"
docker exec uask_orchestrator sh -lc "cd /app && DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/$fresh alembic heads"
```

## One-liner (dev reproduce)

```powershell
docker compose restart && docker exec uask_orchestrator sh -lc "cd /app && alembic stamp --purge 20260216_drop_prompt_ck && alembic upgrade head"
```

