# Implementation Plan — Credit Transfer by Email + Notifications (Minimal Change)

Date: 2026-02-12
Constraint: additive, backward-compatible, no `/solve`/`/chat` contract changes.

## Step 1: Additive DB migrations
1. Create `notifications` table (if absent):
   - `id`, `user_id`, `type`, `title`, `body`, `payload_json`, `severity`, `is_read`, `created_at`, `read_at`, `action_type`, `action_payload`, `dedupe_key`
   - Unique index: `(user_id, dedupe_key)` where `dedupe_key IS NOT NULL`.
2. Create `credit_transfers` table:
   - `id (uuid)`, `sender_user_id`, `recipient_email`, `recipient_user_id nullable`, `amount`, `status`, `idempotency_key`, `created_at`, `updated_at`, `expires_at`, `claimed_at`, `failure_reason`, `sender_ip_hash nullable`
   - Unique index: `(sender_user_id, idempotency_key)`
   - Indexes: `(recipient_email, status)`, `(sender_user_id, created_at)`.
3. No destructive migration; no existing table/column renames.

## Step 2: Config + feature flags (additive)
1. Introduce new config keys via existing `systemconfig` pattern:
   - `CREDIT_TRANSFER_ENABLED`
   - `NOTIFICATIONS_ENABLED`
   - `CREDIT_TRANSFER_MIN`
   - `CREDIT_TRANSFER_MAX`
   - `CREDIT_TRANSFER_DAILY_CAP`
   - `CREDIT_TRANSFER_PENDING_EXPIRY_DAYS`
   - `CREDIT_TRANSFER_PER_MIN_LIMIT`
2. Keep environment fallback for safe boot defaults.

## Step 3: Notifications backend module (isolated)
1. Add new router module for `/api/v1/notifications/*`.
2. Endpoints:
   - `GET /api/v1/notifications`
   - `POST /api/v1/notifications/{id}/read`
   - `POST /api/v1/notifications/read_all`
   - `POST /api/v1/notifications/{id}/thank`
   - `GET /api/v1/notifications/stream` (SSE)
3. Implement dedupe helper for transfer-related emits.
4. Apply route limits for `thank`/`read_all` spam control.

## Step 4: Credit transfer service (atomic + idempotent)
1. Add service `credit_transfer_service.py` using one DB transaction per operation.
2. Reuse existing wallet/ledger write strategy (BillingLedger/CreditLot/CreditHold patterns) instead of separate balance logic.
3. Implement:
   - `create_transfer(sender, recipient_email, amount, idempotency_key)`
   - `claim_pending(user_email)`
   - `expire_and_refund_pending(now)` (job callable)
4. Enforce server checks:
   - feature flag enabled
   - self-transfer forbidden
   - min/max amount
   - daily cap
   - per-minute limits
   - sufficient spendable balance

## Step 5: Credits API endpoints (isolated)
1. Add `/api/v1/credits/transfer`.
2. Add `/api/v1/credits/claim_pending`.
3. Add `/api/v1/credits/balance` returning:
   - `spendable_balance`
   - `pending_outgoing_total`
   - `can_transfer`
   - `min_transfer`, `max_transfer`, `daily_remaining`
   - `reason_if_disabled`
4. Keep existing `/api/v1/credits/estimate` unchanged.

## Step 6: Expiry/refund job
1. Add periodic task in existing Celery beat (no new service):
   - find `PENDING` transfers past expiry
   - refund escrow to sender atomically
   - mark transfer terminal state
   - emit notifications.

## Step 7: Frontend integration (minimal, isolated)
1. Add `NotificationsPanel` component (Solve page only), no changes to solve payload.
2. Add client methods:
   - fetch notifications
   - mark read/read_all/thank
   - SSE subscribe fallback to polling.
3. Add transfer UI block driven only by backend `/api/v1/credits/balance`.
4. Highlight rule: transfer option highlighted only when `can_transfer=true` and enabled flag true.
5. In-flight guard + idempotency key reuse on retries.

## Step 8: Admin config endpoints
1. Add `/api/v1/admin/config/credit_transfer` GET/PUT using existing admin auth dependency.
2. Persist values to `systemconfig` only (no separate config table).

## Step 9: Tests and verification
1. Backend tests:
   - notifications CRUD/read flows + dedupe
   - transfer to existing user (COMPLETED)
   - transfer to unknown email (PENDING)
   - claim pending
   - idempotent retry no double movement
   - concurrency protection under parallel requests
   - daily cap/per-minute limits
   - expiry refund
   - feature flag disabled returns controlled error
2. Frontend tests:
   - highlight/disabled state bound to `/credits/balance`
   - notifications panel load without touching solve payload
3. Smoke checks:
   - `/solve`, `/solve_v3`, `/chat/(id)` unaffected
   - admin routes remain 200
   - lint/typecheck green.

## Step 10: Rollout strategy
1. Deploy with both feature flags OFF.
2. Enable notifications first (`NOTIFICATIONS_ENABLED=true`) for admins/test users.
3. Enable transfer with strict low caps first.
4. Observe ledger, error logs, rate-limit hits, and transfer success/failure mix.

