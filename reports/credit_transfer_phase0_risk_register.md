# Risk Register — Credit Transfer by Email + Notifications

Date: 2026-02-12

## Risks and Mitigations

1. Double-spend under concurrent transfer requests
- Impact: critical balance inconsistency.
- Mitigation: single DB transaction + `FOR UPDATE` lock on sender wallet state + unique idempotency key per sender.

2. Idempotency bypass via regenerated client key
- Impact: repeated transfer execution.
- Mitigation: enforce request replay handling server-side using `(sender_user_id, idempotency_key)` uniqueness and return original transfer result.

3. Split-brain balance logic (new transfer engine diverges from wallet ledger)
- Impact: reconciliation failures.
- Mitigation: reuse existing BillingLedger/CreditLot write path; no new balance source.

4. Pending transfer funds stuck in escrow
- Impact: user dissatisfaction, accounting drift.
- Mitigation: expiry + auto-refund job; admin visibility for pending/expired/refunded transfer states.

5. Notification spam loop (especially thank/action flows)
- Impact: UX degradation and infra load.
- Mitigation: dedupe keys + endpoint rate limits + no recursive notification trigger on thank.

6. Transfer spam abuse by bot accounts
- Impact: fraud, support burden.
- Mitigation: per-minute user/IP limits, daily cap, account-age/good-standing gate.

7. Self-transfer loopholes via email casing/spacing
- Impact: rules bypass.
- Mitigation: canonicalize email (`trim().lower()`) and compare both user_id and normalized email.

8. Credits charged for failed operations
- Impact: trust and refund load.
- Mitigation: strict transactional boundary; only commit ledger moves on valid state transitions; controlled error responses.

9. Existing `/solve` or `/chat` route regression
- Impact: core product outage.
- Mitigation: isolate routers under `/api/v1/credits/*` and `/api/v1/notifications/*`; no payload changes to solve/chat endpoints; regression smoke tests mandatory.

10. Migration rollout failure on production data
- Impact: deploy rollback pressure.
- Mitigation: additive migrations only, idempotent seed/config writes, pre-deploy migration dry run on staging snapshot.

11. Missing recipient account for email transfer
- Impact: transfer cannot complete immediately.
- Mitigation: explicit `PENDING` lifecycle with claim endpoint and expiry-refund path.

12. Unauthorized access to transfer/admin config endpoints
- Impact: security breach.
- Mitigation: reuse existing JWT auth dependencies; admin endpoints use `get_admin_user`.

13. Notification stream instability (SSE disconnects)
- Impact: stale UI state.
- Mitigation: fallback polling every 30s and idempotent mark-read operations.

14. Daily cap miscalculation due timezone boundaries
- Impact: false blocks or over-transfer.
- Mitigation: define server-time UTC window and document it; keep implementation consistent in SQL queries.

15. Performance regression from synchronous write amplification
- Impact: higher DB load.
- Mitigation: narrow indexes, cursor pagination, avoid unnecessary per-hit updates, batch/non-critical updates where possible.

16. Legacy + new billing paths interaction complexity
- Impact: edge-case inconsistencies.
- Mitigation: keep transfer logic on billing v2 ledger path only; add explicit guard when required dependencies not active.

