# Admin Wallet & Programs Fix Report

Date: 2026-02-10

## Restored Routes/Tabs
- `/admin/dashboard` (Overview)
- `/admin/users` (Users)
- `/admin/quotas` (Quotas)
- `/admin/prompts` (Prompts)
- `/admin/prompt-registry` (Prompt Registry)
- `/admin/schema-registry` (Schema Registry)
- `/admin/prompt-bindings` (Prompt Bindings)
- `/admin/content` (Content)
- `/admin/whatsapp-bot` (WhatsApp Bot)
- `/admin/whatsapp-monitor` (WhatsApp Monitor)
- `/admin/social-logs` (Social Logs)
- `/admin/logs` (Logs)
- `/admin/solver-attempts` (Solvers)
- `/admin/billing` (Billing Control)
- `/admin/billing/programs` (Credit Programs)
- `/admin/billing/enrollments` (Enrollments)
- `/admin/billing/pricing` (Pricing Config)
- `/admin/billing/packs` (Credit Packs)
- `/admin/billing/ledger` (Ledger Explorer)
- `/admin/billing/refunds` (Refund Center)
- `/admin/billing/holds` (Active Holds)
- `/admin/billing/health` (Billing Health)
- `/admin/billing/flags` (Feature Flags)
- `/admin/billing/invoices` (Invoices)
- `/admin/billing/legacy` (Legacy Plans - Read Only)
- `/admin/legacy/subscriptions` (Legacy Subscriptions - Read Only)
- `/admin/data` (Data)
- `/admin/system-config` (System Config)

## Admin Nav Manifest (Option A)
- `admin_nav_manifest.json` is the single source of truth for admin navigation.
- Frontend reads `admin_nav_manifest.json` to render the sidebar in `src/app/admin/layout.tsx`.
- Backend smoke test `backend/tests/smoke/test_admin_nav_regression.py` loads the same manifest and validates API health checks listed under `api_checks`.

## Endpoints Implemented/Fixed
- `GET /api/admin/billing/users/{user_id}/wallet_summary` (wallet summary + expiring soon)
- `GET /api/admin/billing/users/{user_id}/wallet` (legacy alias)
- `GET /api/admin/billing/users/{user_id}/lots`
- `GET /api/admin/billing/users/{user_id}/ledger`
- `GET /api/admin/billing/users/{user_id}/enrollments`
- `POST /api/admin/billing/users/{user_id}/grant`
- `POST /api/admin/billing/users/{user_id}/refund`
- `POST /api/admin/billing/users/{user_id}/reconcile`
- `POST /api/admin/billing/users/{user_id}/enroll`
- `POST /api/admin/billing/users/{user_id}/unenroll`
- `POST /api/admin/billing/users/{user_id}/program-grant`
- `GET /api/admin/billing/holds`
- `POST /api/admin/billing/holds/{hold_id}/release`
- `GET /api/admin/billing/programs`
- `POST /api/admin/billing/programs`
- `GET /api/admin/billing/pricing`
- `POST /api/admin/billing/pricing`
- `GET /api/admin/billing/invoices`
- `GET /api/admin/billing/flags` (now on `/api` prefix; legacy `/admin/billing/flags` preserved)

## DEV Workflow Fix
- `scripts/dev_recreate_db_and_seed.py` now defaults `APP_ENV=DEV` when missing and still requires `--confirm RESET_DEV_DB`.

## DEV Seed (Superadmin)
- DEV seed now ensures exactly one superadmin (default `admin@uask.ai`).
- PROD/STAGING will not auto-create superadmin unless explicitly provided via `SEED_INTERNAL_USERS_JSON`.

## Legacy Plan/Subs Safety
- Legacy plan mutation endpoints return `410 Gone`.
- Smoke test `backend/tests/smoke/test_legacy_plan_mutations.py` enforces non-mutation.

## Screenshots
- Pending: please capture and provide file paths for:
  - User wallet before grant/refund (lots + ledger visible)
  - User wallet after grant/refund (lots + ledger visible)
  - Credit programs CRUD page (list + create/edit/deactivate)

## API Response Snippets
Grant/Refund network proof (TestClient calls returned 200):

```
WALLET_SUMMARY_BEFORE 200
{'user_id': 941, 'user_email': 'admin@uask.ai', 'cached_balance': 1024.0, 'computed_balance': 1024.0, 'delta': 0.0, 'total_lots': 5, 'active_lots': 5, 'pending_holds': 0, 'pending_hold_credits': 0.0, 'expiring_soon_credits': 20.0, 'expiring_soon_lots': 2}

GRANT_RESPONSE 200
{'success': True, 'wallet_summary': {'user_id': 941, 'user_email': 'admin@uask.ai', 'cached_balance': 1036.5, 'computed_balance': 1036.5, 'delta': 0.0, 'total_lots': 6, 'active_lots': 6, 'pending_holds': 0, 'pending_hold_credits': 0.0, 'expiring_soon_credits': 20.0, 'expiring_soon_lots': 2}, 'lot': {'id': 944, 'lot_type': 'ADJUSTMENT', 'credits_total': 12.5, 'credits_remaining': 12.5, 'status': 'ACTIVE', 'source_program_id': None, 'source_payment_id': None, 'source_attempt_id': None, 'reason_code': 'Admin grant proof', 'purchased_at': '2026-02-10T02:32:13.409066', 'expires_at': '2026-04-11T02:32:13.409072', 'created_at': '2026-02-10T02:32:13.409494', 'source_label': 'ADMIN:941 AUDIT:21', 'source_meta': {'admin_user_id': '941', 'admin_audit_log_id': '21'}}, 'ledger_id': 21}

REFUND_RESPONSE 200
{'success': True, 'wallet_summary': {'user_id': 941, 'user_email': 'admin@uask.ai', 'cached_balance': 1039.5, 'computed_balance': 1039.5, 'delta': 0.0, 'total_lots': 7, 'active_lots': 7, 'pending_holds': 0, 'pending_hold_credits': 0.0, 'expiring_soon_credits': 20.0, 'expiring_soon_lots': 2}, 'lot': {'id': 945, 'lot_type': 'REFUND', 'credits_total': 3.0, 'credits_remaining': 3.0, 'status': 'ACTIVE', 'source_program_id': None, 'source_payment_id': 'pay_proof_001', 'source_attempt_id': 'attempt_proof_001', 'reason_code': 'SERVICE_ISSUE', 'purchased_at': '2026-02-10T02:32:13.437581', 'expires_at': '2026-04-11T02:32:13.437570', 'created_at': '2026-02-10T02:32:13.437938', 'source_label': 'REFUND:attempt_proof_001 AUDIT:22', 'source_meta': {'refund_ref': 'attempt_proof_001', 'admin_user_id': '941', 'admin_audit_log_id': '22'}}, 'ledger_id': 22}

WALLET_SUMMARY_AFTER 200
{'user_id': 941, 'user_email': 'admin@uask.ai', 'cached_balance': 1039.5, 'computed_balance': 1039.5, 'delta': 0.0, 'total_lots': 7, 'active_lots': 7, 'pending_holds': 0, 'pending_hold_credits': 0.0, 'expiring_soon_credits': 20.0, 'expiring_soon_lots': 2}
```

## SQL Outputs
```
SQL: creditlot
(945, 'REFUND', Decimal('3.0000000000'), Decimal('3.0000000000'), 'ACTIVE', 'pay_proof_001', 'attempt_proof_001', 'SERVICE_ISSUE', datetime.datetime(2026, 2, 10, 2, 32, 13, 437938))
(944, 'ADJUSTMENT', Decimal('12.5000000000'), Decimal('12.5000000000'), 'ACTIVE', None, None, 'Admin grant proof', datetime.datetime(2026, 2, 10, 2, 32, 13, 409494))
(943, 'REFUND', Decimal('2.0000000000'), Decimal('2.0000000000'), 'ACTIVE', 'pay_smoke_1770690688', 'attempt_smoke_1770690688', 'SERVICE_ISSUE', datetime.datetime(2026, 2, 10, 2, 31, 28, 495515))
(942, 'ADJUSTMENT', Decimal('10.0000000000'), Decimal('10.0000000000'), 'ACTIVE', None, None, 'smoke grant', datetime.datetime(2026, 2, 10, 2, 31, 28, 469703))
(941, 'REFUND', Decimal('2.0000000000'), Decimal('2.0000000000'), 'ACTIVE', 'pay_smoke_1770690611', 'attempt_smoke_1770690611', 'SERVICE_ISSUE', datetime.datetime(2026, 2, 10, 2, 30, 11, 424620))

SQL: billingledger
(22, 'ADMIN_REFUND', Decimal('3.0000000000'), Decimal('1036.5000000000'), Decimal('1039.5000000000'), 'attempt_proof_001', 'refund_proof_941', datetime.datetime(2026, 2, 10, 2, 32, 13, 440232))
(21, 'ADMIN_ADJUSTMENT', Decimal('12.5000000000'), Decimal('1024.0000000000'), Decimal('1036.5000000000'), None, 'grant_proof_941', datetime.datetime(2026, 2, 10, 2, 32, 13, 413435))
(20, 'ADMIN_REFUND', Decimal('2.0000000000'), Decimal('1022.0000000000'), Decimal('1024.0000000000'), 'attempt_smoke_1770690688', 'smoke_refund_941_1770690688', datetime.datetime(2026, 2, 10, 2, 31, 28, 497558))
(19, 'ADMIN_ADJUSTMENT', Decimal('10.0000000000'), Decimal('1012.0000000000'), Decimal('1022.0000000000'), None, 'smoke_grant_941_1770690688', datetime.datetime(2026, 2, 10, 2, 31, 28, 473414))
(18, 'ADMIN_REFUND', Decimal('2.0000000000'), Decimal('1010.0000000000'), Decimal('1012.0000000000'), 'attempt_smoke_1770690611', 'smoke_refund_941_1770690611', datetime.datetime(2026, 2, 10, 2, 30, 11, 426971))

SQL: adminauditlog
(22, 'CREDIT_REFUND', '945', 941, 'Admin refund proof', datetime.datetime(2026, 2, 10, 2, 32, 13, 441343))
(21, 'CREDIT_LOT', '944', 941, 'Admin grant proof', datetime.datetime(2026, 2, 10, 2, 32, 13, 415857))
(20, 'CREDIT_REFUND', '943', 941, 'smoke refund', datetime.datetime(2026, 2, 10, 2, 31, 28, 498450))
(19, 'CREDIT_LOT', '942', 941, 'smoke grant', datetime.datetime(2026, 2, 10, 2, 31, 28, 476161))
(18, 'RECONCILIATION', '941', 941, 'smoke test reconcile', datetime.datetime(2026, 2, 10, 2, 30, 13, 742593))
```

## Tests
Required workflow commands executed:
- `docker compose exec orchestrator python scripts/dev_recreate_db_and_seed.py --confirm RESET_DEV_DB`
- `docker compose exec orchestrator alembic current`
  - Output: `7aa5b3a25e41 (head)`
- `docker compose exec orchestrator pytest tests/seeding/ -q`
  - Output: `4 passed`
- `docker compose exec orchestrator pytest tests/smoke/ -q`
  - Output: `12 passed` (0 skipped)

Smoke coverage additions:
- `backend/tests/smoke/test_admin_nav_regression.py` validates `admin_nav_manifest.json` + API checks.
- `backend/tests/smoke/test_admin_routes.py` includes superadmin-only grant/refund.
- `backend/tests/smoke/test_legacy_plan_mutations.py` enforces legacy mutation endpoints return 410/403.

## Migrations Added
- None.

## Notes
- Superadmin seeding is handled in DEV via seed logic (no manual DB edits).
