# uaskstudents

## DEV Reset & Seed

Use `orchestrator` (not `backend`) for migration/scripts.

### One-command DEV NUKE + reseed + smoke

```bash
docker compose up -d postgres redis orchestrator
docker compose exec orchestrator alembic upgrade head
docker compose exec orchestrator python scripts/dev_seed_and_smoke_test.py
```

### Manual DEV flow

```bash
docker compose up -d postgres redis orchestrator
docker compose exec orchestrator python scripts/dev_reset_db.py --mode NUKE --confirm RESET_DEV_DB
docker compose exec orchestrator alembic upgrade head
docker compose exec orchestrator python scripts/seed_production.py --env DEV
docker compose exec orchestrator pytest tests/smoke/ -q
```

### DEV reset modes

- `NUKE`: truncates all public tables except `alembic_version`, then migration + reseed.
- `SAFE`: truncates non-essential operational tables while preserving seeded reference/config tables.

Both modes are blocked unless `APP_ENV=DEV` or `ALLOW_DESTRUCTIVE_DEV_RESET=true`.

## PROD Seeding Rules

`python scripts/seed_production.py --env PROD`

Safety guarantees:

- No destructive reset logic is present in production seeder.
- Seeder only touches allowlisted essential tables:
  `school`, `prompt_bindings`, `prompt_templates`, `providermodelpricing`,
  `systemconfig`, `plan`, `creditprogramdefinition`, `payment` (table only), `user`.
- Seeder never inserts payment transactions; it fails if `payment` has rows added by seed flow.
- Internal user seeding in `PROD`/`STAGING` requires `SEED_INTERNAL_USERS_JSON` with passwords.
- Password overwrite for existing internal users is refused unless `--rotate-passwords` is passed.
- DEV fixtures (`--dev-fixtures`) are refused in `PROD`/`STAGING`.
- Seed idempotency is tracked in `seed_registry` using `(seed_name, seed_version, checksum)`.

## WhatsApp Feature Flags

These are OFF by default and must be explicitly enabled:

- `WHATSAPP_OCR_ENABLED=false`
- `WHATSAPP_SOLVER_V3_ENABLED=false`
- `WHATSAPP_INTERNAL_KEY=`
- `WHATSAPP_INTERNAL_PORT=8791`

## LLM Provider Configuration

- `LLM_PROVIDER=openai|ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=qwen25-math7b:latest`
- `OLLAMA_TIMEOUT_SECONDS=60`
- `OLLAMA_CONNECT_TIMEOUT_SECONDS=5`
- `OLLAMA_MAX_TOKENS=` (optional)
- `OLLAMA_TEMPERATURE=0.2`
- `OLLAMA_NUM_CTX=4096`
