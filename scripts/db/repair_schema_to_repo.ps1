param(
    [string]$DbUser = "uask_user",
    [string]$DbName = "uask_db",
    [string]$BaselineRevision = "20260216_drop_prompt_ck"
)

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

New-Item -ItemType Directory -Path backups -Force | Out-Null
New-Item -ItemType Directory -Path reports/db_repair -Force | Out-Null

Write-Host "[1/4] Backup DB..."
docker exec uask_postgres sh -lc "pg_dump -U $DbUser -d $DbName -Fc -f /tmp/db_full_$ts.dump"
docker exec uask_postgres sh -lc "pg_dump -U $DbUser -d $DbName --schema-only -f /tmp/db_schema_$ts.sql"
docker cp uask_postgres:/tmp/db_full_$ts.dump backups/db_full_$ts.dump
docker cp uask_postgres:/tmp/db_schema_$ts.sql backups/db_schema_$ts.sql

Write-Host "[2/4] Capture pre-repair state..."
docker exec uask_postgres psql -U $DbUser -d $DbName -c "SELECT version_num FROM alembic_version;" | Out-File -Encoding utf8 reports/db_repair/pre_alembic_version.txt

Write-Host "[3/4] Repair Alembic version chain..."
docker exec uask_orchestrator sh -lc "cd /app && alembic stamp --purge $BaselineRevision"
docker exec uask_orchestrator sh -lc "cd /app && alembic upgrade head"

Write-Host "[4/4] Capture post-repair state..."
docker exec uask_postgres psql -U $DbUser -d $DbName -c "SELECT version_num FROM alembic_version;" | Out-File -Encoding utf8 reports/db_repair/post_alembic_version.txt
docker exec uask_orchestrator sh -lc "cd /app && alembic current" | Out-File -Encoding utf8 reports/db_repair/post_alembic_current.txt
docker exec uask_orchestrator sh -lc "cd /app && alembic heads" | Out-File -Encoding utf8 reports/db_repair/post_alembic_heads.txt

Write-Host "Repair completed."
