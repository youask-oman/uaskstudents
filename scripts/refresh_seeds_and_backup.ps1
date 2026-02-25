param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$SkipDockerRestart,
    [switch]$KeepOldBackups,
    [switch]$KeepOldSchemaArtifacts
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Invoke-Checked([string]$command) {
    Write-Host "[cmd] $command"
    cmd /c $command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $command"
    }
}

function Require-Tool([string]$toolName) {
    if (-not (Get-Command $toolName -ErrorAction SilentlyContinue)) {
        throw "Required tool not found in PATH: $toolName"
    }
}

Require-Tool "docker"
Require-Tool "python"

Set-Location $ProjectRoot

$composeFile = Join-Path $ProjectRoot "docker-compose.yml"
if (-not (Test-Path $composeFile)) {
    throw "docker-compose.yml not found at $composeFile"
}

$backendDir = Join-Path $ProjectRoot "backend"
$seedDataDir = Join-Path $backendDir "seed_data"
$backupsDir = Join-Path $ProjectRoot "backups"
$dbRepairDir = Join-Path $ProjectRoot "reports\db_repair"

New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null

Write-Step "Ensuring compose services are running"
Invoke-Checked "docker compose -f `"$composeFile`" up -d"

Write-Step "Refreshing seed_data from current database"
if (Test-Path (Join-Path $seedDataDir "*.json")) {
    Get-ChildItem -File (Join-Path $seedDataDir "*.json") | ForEach-Object { Remove-Item -Force $_.FullName }
}
$env:PYTHONPATH = "backend"
python (Join-Path $backendDir "scripts\export_prompt_and_schema_seeds.py") --out $seedDataDir
if ($LASTEXITCODE -ne 0) {
    throw "Seed export failed."
}

Write-Step "Applying latest DB migrations"
Push-Location $backendDir
alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "Alembic migration failed."
}
Pop-Location

if (-not $KeepOldBackups) {
    Write-Step "Deleting old backup files"
    if (Test-Path (Join-Path $backupsDir "uask_db_*.dump")) {
        Get-ChildItem -File (Join-Path $backupsDir "uask_db_*.dump") | ForEach-Object { Remove-Item -Force $_.FullName }
    }
    if (Test-Path (Join-Path $backupsDir "uask_db_*.sql")) {
        Get-ChildItem -File (Join-Path $backupsDir "uask_db_*.sql") | ForEach-Object { Remove-Item -Force $_.FullName }
    }
    if (Test-Path (Join-Path $backupsDir "uask_db_*_verify.json")) {
        Get-ChildItem -File (Join-Path $backupsDir "uask_db_*_verify.json") | ForEach-Object { Remove-Item -Force $_.FullName }
    }
}

if (-not $KeepOldSchemaArtifacts) {
    Write-Step "Deleting old schema dump artifacts"
    if (Test-Path (Join-Path $backendDir "final_schema_dump*.json")) {
        Get-ChildItem -File (Join-Path $backendDir "final_schema_dump*.json") | ForEach-Object { Remove-Item -Force $_.FullName }
    }
    if (Test-Path (Join-Path $dbRepairDir "*.sql")) {
        Get-ChildItem -File (Join-Path $dbRepairDir "*.sql") | ForEach-Object { Remove-Item -Force $_.FullName }
    }
}

Write-Step "Creating fresh DB backups (dump/sql/schema)"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFile = Join-Path $backupsDir "uask_db_${ts}.dump"
$sqlFile = Join-Path $backupsDir "uask_db_${ts}.sql"
$schemaFile = Join-Path $backupsDir "uask_db_${ts}_schema.sql"
$verifyFile = Join-Path $backupsDir "uask_db_${ts}_verify.json"

# Binary dump: redirect through cmd so bytes are preserved.
Invoke-Checked "docker compose -f `"$composeFile`" exec -T postgres pg_dump -U uask_user -d uask_db -F c > `"$dumpFile`""
Invoke-Checked "docker compose -f `"$composeFile`" exec -T postgres pg_dump -U uask_user -d uask_db -F p > `"$sqlFile`""
Invoke-Checked "docker compose -f `"$composeFile`" exec -T postgres pg_dump -U uask_user -d uask_db -s -F p > `"$schemaFile`""

if ((Get-Item $dumpFile).Length -le 0) { throw "Dump file is empty: $dumpFile" }
if ((Get-Item $sqlFile).Length -le 0) { throw "SQL file is empty: $sqlFile" }
if ((Get-Item $schemaFile).Length -le 0) { throw "Schema SQL file is empty: $schemaFile" }

Write-Step "Verifying backup integrity"
$containerTmp = "/tmp/$(Split-Path $dumpFile -Leaf)"
Invoke-Checked "docker cp `"$dumpFile`" uask_postgres:$containerTmp"
$restoreList = cmd /c "docker compose -f `"$composeFile`" exec -T postgres pg_restore -l $containerTmp"
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore list verification failed."
}
Invoke-Checked "docker compose -f `"$composeFile`" exec -T postgres rm -f $containerTmp"

$hashDump = (Get-FileHash -Algorithm SHA256 $dumpFile).Hash
$hashSql = (Get-FileHash -Algorithm SHA256 $sqlFile).Hash
$hashSchema = (Get-FileHash -Algorithm SHA256 $schemaFile).Hash

$tableCountsRaw = @'
import json
from sqlmodel import Session
from sqlalchemy import text
from app.database import engine
q = text("SELECT relname, n_live_tup::bigint FROM pg_stat_user_tables ORDER BY relname")
out = []
with Session(engine) as s:
    for row in s.execute(q).all():
        out.append({"table": row[0], "rows_estimate": int(row[1] or 0)})
print(json.dumps(out))
'@ | python -

if ($LASTEXITCODE -ne 0) {
    throw "Failed to collect table counts."
}

$tableCounts = $tableCountsRaw | ConvertFrom-Json
$verify = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    files = [ordered]@{
        dump = [ordered]@{
            path = $dumpFile
            bytes = (Get-Item $dumpFile).Length
            sha256 = $hashDump
        }
        sql = [ordered]@{
            path = $sqlFile
            bytes = (Get-Item $sqlFile).Length
            sha256 = $hashSql
        }
        schema_sql = [ordered]@{
            path = $schemaFile
            bytes = (Get-Item $schemaFile).Length
            sha256 = $hashSchema
        }
    }
    pg_restore_list_entries = ($restoreList | Measure-Object -Line).Lines
    table_counts_estimate = $tableCounts
}
$verify | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $verifyFile

if (-not $SkipDockerRestart) {
    Write-Step "Restarting docker compose stack"
    Invoke-Checked "docker compose -f `"$composeFile`" down"
    Invoke-Checked "docker compose -f `"$composeFile`" up -d"
}

Write-Step "Final service snapshot"
docker compose -f "$composeFile" ps -a --format json

Write-Step "Completed"
Write-Host "Seed data refreshed: $seedDataDir"
Write-Host "Backup dump: $dumpFile"
Write-Host "Backup sql: $sqlFile"
Write-Host "Schema sql: $schemaFile"
Write-Host "Verification: $verifyFile"
