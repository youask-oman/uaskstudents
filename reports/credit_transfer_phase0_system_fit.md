# System Fit Report — Credit Transfer by Email + Notifications (Phase 0)

Date: 2026-02-12
Scope: Discovery only (no feature coding)

## A) Codebase Map

### Backend entrypoints and routers
- App bootstrap: `backend/app/main.py`
- Primary API router: `backend/app/api.py` mounted at `/api/v1`
- Existing billing/wallet routers:
  - `backend/app/api_billing.py` mounted at `/api/v1/billing`
  - `backend/app/api_wallet.py` mounted at `/api/v1/wallet`
  - `backend/app/bg_routers/credits_router.py` mounted at `/api/v1/credits` (currently estimate-focused)
- Admin routes:
  - `backend/app/api_admin.py`
  - `backend/app/admin_billing/*`

### DB models location
- Main SQLModel definitions: `backend/app/models/__init__.py`
- Additional billing/program models: `backend/app/models/credit_program_models.py`

### Migrations location and conventions
- Alembic config: `backend/alembic.ini`
- Migration env: `backend/alembic/env.py`
- Revisions: `backend/alembic/versions/*.py`
- Convention observed: timestamp/purpose-oriented revision filenames with explicit `upgrade()`/`downgrade()`.

### Auth middleware/dependencies
- Login issues JWT + `session_token`: `backend/app/api.py:1615` (`/api/v1/login`)
- Bearer auth dependency patterns:
  - `backend/app/api_admin.py:get_current_user`
  - `backend/app/admin_billing/deps.py:get_current_user`
  - `backend/app/api_billing.py:get_current_user`
- Terms gate middleware on authenticated API traffic: `backend/app/main.py` (`enforce_terms_acceptance`).

### Request trace / attempt correlation
- Request middleware sets `trace_id` and optional `request_id` from `X-Request-ID`: `backend/app/main.py`
- Trace context container: `backend/app/trace.py`
- Solve pipeline uses and stores request/attempt identifiers in `SolverOutputAttempt` and payload/runtime meta (`backend/app/services/solve/superset_v2_pipeline.py`, `backend/app/api.py` attempt endpoints).

### Existing credit handling (source of truth)
- Core balance/cached fields on user: `user.credits_balance`.
- Core wallet accounting objects:
  - `CreditLot` (available credits buckets)
  - `CreditLotConsumption` (lot-level debit/refund records)
  - `CreditHold` (temporary reserve)
  - `BillingLedger` (transaction ledger)
  - `UsageLedger` + `Subscription` (legacy coexistence path)
- Production-grade settlement service exists and uses row locks: `backend/app/services/billing_ledger_service_v2.py`
  - Documented with `SELECT ... FOR UPDATE`
  - Hold ? settle/release workflow
  - Idempotency fields in ledger/holds

### Existing notification-like patterns
- No general `notifications` table currently in `public` schema.
- Existing SSE is feature-specific only:
  - WhatsApp monitor stream: `backend/app/api_admin.py` / `backend/app/api.py`
  - Solve attempt event stream: `backend/app/api.py` (attempt events)
- No user-facing in-app notification API currently.

### Existing async infra
- Redis configured (`REDIS_URL`) in docker compose.
- Celery worker + beat in same codebase (`backend/app/worker.py`) with queues (`celery`, `whatsapp`) and periodic jobs.

### Existing rate limiting
- Global limiter wiring via `slowapi` in `backend/app/main.py` + `backend/app/api.py`.
- Several endpoint decorators use `@limiter.limit(...)`.
- Additional manual endpoint-specific throttling exists in some routers (e.g., `snap_solve_pdf`).

## B) Database Truth (Live Postgres)

Executed against live `uask_db`.

### 1) Tables
Command:
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema='public'
ORDER BY 1;
```
Result summary:
- 77 tables in `public`.
- Relevant to this feature include: `user`, `billingledger`, `creditlot`, `creditlotconsumption`, `credithold`, `usageledger`, `requestevent`, `solveroutputattempt`, `systemconfig`.
- No `notifications` or `credit_transfers` table currently.

### 2) Relevant columns (credit/balance/ledger/notif/transaction/email)
Command:
```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public'
  AND (
    column_name ILIKE '%credit%'
    OR column_name ILIKE '%balance%'
    OR column_name ILIKE '%ledger%'
    OR column_name ILIKE '%notif%'
    OR column_name ILIKE '%transaction%'
    OR column_name ILIKE '%email%'
  )
ORDER BY table_name, column_name;
```
Result highlights:
- `user.email`, `user.credits_balance`
- `billingledger.*credits*` fields (`credits_before`, `credits_after`, `delta_credits`, etc.)
- `creditlot.credits_total`, `creditlot.credits_remaining`
- `credithold.reserved_credits`
- `subscription.credits_balance`, `subscription.credits_used_this_period`
- No existing notification-specific columns/tables.

### 3) Confirm user table
Command:
```sql
SELECT id, email FROM public."user" LIMIT 5;
```
Sample rows returned successfully (e.g., `e2e_contract@uask.ai`, `loai@uask.ai`, etc.).

## C) API Contract Check

### Auth/session extraction
- API uses bearer JWT auth (`Authorization: Bearer <token>`).
- Login returns both JWT and `session_token` (`/api/v1/login`).
- Session token currently used in heartbeat/online-session semantics; auth remains JWT-driven.

### request_id / attempt_id propagation
- Request-level `request_id` can be injected via `X-Request-ID` and is traced in middleware logs.
- Solve v3 pipelines generate/persist `request_id` + `attempt_id` and expose them via response and attempt endpoints (`/api/v1/attempt/{attempt_id}`).

### Current frontend credit balance retrieval
- Frontend wallet API client: `src/lib/wallet.ts`
- Balance summary fetched from `/api/v1/wallet/summary`.
- Solve/Profile/Navbar/Layout rely on this summary for displayed credits/tier/holds.

## D) Safety Plan (Required)

### Idempotency approach
- Transfer create endpoint requires `idempotency_key` (client-provided UUID).
- Enforce unique constraint: `(sender_user_id, idempotency_key)` on `credit_transfers`.
- On duplicate key, return original transfer result without re-applying ledger moves.

### Concurrency locking approach
- Use DB transaction with row locking on sender wallet state.
- Prefer existing proven lock strategy from billing V2 (`FOR UPDATE` on sender/user + impacted rows).
- All debit/escrow insertions and transfer row state transitions in one transaction boundary.

### Escrow approach for pending transfer
- New additive transfer lifecycle:
  - Create transfer: sender debited, escrow credited (ledger-balanced move), `status=PENDING` if recipient account absent.
  - Claim pending: escrow debited, recipient credited, `status=COMPLETED`.
  - Expiry/refund: escrow debited, sender credited, `status=EXPIRED` + `REFUNDED` semantics.
- Keep existing wallet ledger as source of truth; do not introduce parallel balance engine.

### Anti-abuse limits
- Server-enforced (never client-only):
  - min/max transfer amount
  - sender daily cap
  - per-minute sender rate cap
  - optional per-IP cap if request IP available
  - self-transfer block by `user_id` and normalized email
  - pending expiry (`N` days)
  - account-age/good-standing gate (configurable)

### Notification abuse prevention
- Add dedupe key semantics with unique `(user_id, dedupe_key)` for event-style notifications.
- Throttle mutating actions (`thank`, `read_all`) with route limits.
- Prevent transfer spam duplicates by transfer-id-based dedupe keys on sender/recipient notifications.

## Fit Conclusion
- The codebase is a good fit for additive implementation.
- Existing wallet/ledger and row-lock patterns can be reused for atomic transfer safety.
- No generic notifications domain exists yet, so notifications must be introduced as additive module.
- Feature can be isolated under `/api/v1/credits/*` and `/api/v1/notifications/*` without touching `/solve` and `/chat/(id)` contracts.

