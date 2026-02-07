# Production Hardening: System Stability, DB Health, Error Tracing, and Observability

**Status**: Phase 1 Complete (Tracing & Error Infrastructure)  
**Last Updated**: 2026-02-06

---

## Overview

This document describes the stability and health layer implemented for the uask.ai payment and billing system. The goal is to ensure production readiness through:

1. **Centralized Error Tracing** with correlation IDs
2. **Automated Reconciliation Jobs** to detect drift and inconsistencies
3. **Admin Health Dashboard** for monitoring and triage
4. **Alerting Hooks** for critical issues

---

## 1. Centralized Error Tracing

### TraceContext (`app/trace.py`)

Every request now has a unique `trace_id` that propagates through:
- API middleware
- Service layers
- Background jobs
- Stripe webhook processing

**Usage**:
```python
from app.trace import TraceContext

# Set context (done automatically in middleware)
TraceContext.set(trace_id="uuid", request_id="req_123", user_id=42)

# Get context anywhere
context = TraceContext.get_all()
# Returns: {"trace_id": "...", "request_id": "...", "user_id": ..., "subscription_id": ...}
```

### Enhanced SystemErrorEntry

**New Fields**:
- `trace_id`: Links error to specific request flow
- `request_id`: Solver request ID if applicable
- `user_id`: User who triggered the error
- `error_code`: Structured error classification (e.g., `payment_webhook_failed`)
- `fingerprint`: SHA256 hash for deduplication
- `occurrence_count`: Number of times this exact error occurred
- `last_seen_at`: Most recent occurrence timestamp

**Error Codes** (Taxonomy):
- `schema_validation_failed`: Pydantic validation errors
- `payment_webhook_failed`: Stripe webhook processing failure
- `ledger_reconcile_mismatch`: Credit balance drift detected
- `invoice_mirror_mismatch`: Invoice inconsistency
- `credit_hold_stuck`: Hold not released after threshold
- `topup_invoice_missing`: Fulfilled order without invoice
- `refund_adjustment_missing`: Refunded invoice without credit note

### ErrorService (`app/services/error_service.py`)

Centralized error capture with automatic fingerprinting and deduplication:

```python
from app.services.error_service import error_service

# Capture exception
try:
    risky_operation()
except Exception as e:
    error_service.capture_exception(
        session=session,
        component="PaymentProcessor",
        exception=e,
        severity="HIGH",
        error_code="payment_webhook_failed",
        context={"stripe_event_id": "evt_123"}
    )

# Capture error without exception
error_service.capture_error(
    session=session,
    component="LedgerReconciliation",
    message="Balance mismatch detected",
    severity="CRITICAL",
    error_code="ledger_reconcile_mismatch",
    context={"subscription_id": 42, "mismatch": 5.0}
)
```

**Deduplication**: Errors with the same fingerprint within 24h are merged, incrementing `occurrence_count`.

**Alerting**: Errors with severity `HIGH` or `CRITICAL` trigger alert dispatch (currently logs, can be extended to Email/Slack).

---

## 2. Reconciliation Jobs

### Ledger Balance Reconciliation (`scripts/reconcile_ledgers_job.py`)

**Purpose**: Detect credit drift by comparing UsageLedger transactions with CreditLot balances.

**Logic**:
```
expected_remaining = total_lot_credits - usage_debits + usage_credits
actual_remaining = sum(CreditLot.credits_remaining WHERE status=ACTIVE)

if abs(expected - actual) > 0.01:
    CREATE ReconciliationFinding(severity=HIGH)
```

**Run**:
```bash
python backend/scripts/reconcile_ledgers_job.py
```

**Output**:
```
=== LEDGER RECONCILIATION REPORT ===
Trace ID: 28b4b059-e34e-4c93-87...
Duration: 1.23s
Subscriptions Checked: 150
Mismatches Found: 0
✓ No issues found. Ledger is healthy.
```

### Invoice Consistency Reconciliation (`scripts/reconcile_invoices_job.py`)

**Checks**:
1. Every `TopUpOrder(status=FULFILLED)` has exactly 1 `Invoice(kind=TOPUP, status=PAID)`
2. Every `Invoice(status=REFUNDED)` has a corresponding `Invoice(kind=ADJUSTMENT)`

**Run**:
```bash
python backend/scripts/reconcile_invoices_job.py
```

### Credit Hold Cleanup (`scripts/cleanup_stale_credit_holds_job.py`)

**Purpose**: Release holds stuck in `HELD` status for >30 minutes (configurable).

**Run**:
```bash
python backend/scripts/cleanup_stale_credit_holds_job.py --threshold 30
```

---

## 3. ReconciliationFinding Model

Tracks issues found during automated reconciliation:

**Fields**:
- `finding_type`: e.g., `ledger_balance_mismatch`, `topup_invoice_missing`
- `severity`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `entity_type`: `subscription`, `request`, `user`, `invoice`, `lot`
- `entity_id`: Primary key or external ID
- `trace_id`: Links to trace context
- `details_json`: Full diagnostic info
- `status`: `OPEN`, `ACKED`, `RESOLVED`
- `resolved_at`, `resolved_by`: Audit trail

---

## 4. Admin Health Dashboard

### API Endpoints (`app/api_admin_health.py`)

**Base Path**: `/api/admin/health`

#### GET `/db`
Database health check:
```json
{
  "connection_ok": true,
  "timestamp": "2026-02-06T17:24:00Z",
  "table_count": 45,
  "sample_table_sizes": {
    "user": 1523,
    "subscription": 520,
    "creditlot": 2341
  }
}
```

#### GET `/findings`
List reconciliation findings:
```
?status=OPEN&severity=HIGH&page=1&page_size=25
```

#### POST `/findings/{finding_id}/resolve`
Mark finding as resolved (admin only).

#### GET `/errors`
List system errors with filtering:
```
?severity=HIGH&error_code=payment_webhook_failed&hours=24
```

#### GET `/errors/summary`
Error summary by code and severity:
```json
{
  "hours": 24,
  "by_error_code": [
    {"error_code": "payment_webhook_failed", "unique_errors": 3, "total_occurrences": 15},
    {"error_code": "ledger_reconcile_mismatch", "unique_errors": 1, "total_occurrences": 1}
  ],
  "by_severity": [
    {"severity": "HIGH", "count": 4},
    {"severity": "ERROR", "count": 12}
  ]
}
```

#### GET `/stripe/failed`
List failed Stripe event processing.

#### GET `/holds/stuck`
Get credit holds stuck in HELD status:
```
?threshold_minutes=30
```

#### POST `/reconcile/ledgers`
Manually trigger ledger reconciliation (admin only).

#### POST `/reconcile/invoices`
Manually trigger invoice reconciliation (admin only).

#### POST `/cleanup/holds`
Manually trigger hold cleanup (admin only).

---

## 5. Structured Logging

All logs now include trace fields when available:

```json
{
  "timestamp": "2026-02-06T17:24:00Z",
  "level": "INFO",
  "message": "Incoming: POST /api/v1/solve",
  "module": "main",
  "trace_id": "28b4b059-e34e-4c93-87...",
  "request_id": "req_abc123",
  "user_id": 42
}
```

Enable JSON logging:
```bash
export USE_JSON_LOGGING=true
```

---

## 6. On-Call Playbook

### High-Severity Finding Detected

1. **Check `/api/admin/health/findings?status=OPEN&severity=HIGH`**
2. **Identify entity**: Note `entity_type` and `entity_id`
3. **Review details**: Check `details_json` for diagnostic info
4. **Trace request**: Use `trace_id` to find related logs
5. **Resolve**:
   - If false positive: Mark as `ACKED`
   - If real issue: Fix root cause, then mark `RESOLVED`

### Ledger Balance Mismatch

**Symptoms**: `finding_type=ledger_balance_mismatch`

**Diagnosis**:
```json
{
  "subscription_id": 42,
  "expected_remaining": 100.0,
  "actual_lot_balance": 95.0,
  "mismatch_amount": 5.0,
  "usage_debits": 50.0,
  "usage_credits": 10.0
}
```

**Actions**:
1. Check `UsageLedger` for subscription
2. Check `CreditLot` for user
3. Look for missing/duplicate transactions
4. If data corruption: Create manual adjustment
5. If logic bug: Fix code, add test

### Stuck Credit Holds

**Symptoms**: `finding_type=credit_hold_stuck`

**Actions**:
1. Check request status via `request_id`
2. If request completed: Hold should have been released (bug)
3. If request failed: Hold should have been released (bug)
4. Run cleanup job to release: `POST /api/admin/health/cleanup/holds`

### Failed Stripe Webhook

**Symptoms**: `error_code=payment_webhook_failed`

**Actions**:
1. Get event ID from `context_json`
2. Check `/api/admin/health/stripe/failed`
3. Review `process_error` field
4. Replay event: `POST /api/admin/payments/stripe/events/{event_id}/replay`

---

## 7. Alerting (Stubbed)

Current implementation logs alerts to console. To enable Email/Slack:

1. **Add config**:
```python
# .env
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=ops@uask.ai
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/...
```

2. **Implement dispatcher**:
```python
# app/services/alert_service.py
def dispatch_alert(entry: SystemErrorEntry):
    if os.getenv("ALERT_EMAIL_ENABLED"):
        send_email(...)
    if os.getenv("ALERT_SLACK_WEBHOOK"):
        send_slack(...)
```

3. **Update ErrorService**:
```python
def _dispatch_alert(self, entry: SystemErrorEntry):
    from app.services.alert_service import dispatch_alert
    dispatch_alert(entry)
```

---

## 8. Next Steps (Phase 2)

- [ ] Add DB constraints (unique indexes on critical fields)
- [ ] Implement BillingLedger vs UsageLedger consistency check
- [ ] Add stress tests for concurrency safety
- [ ] Build frontend Health Dashboard UI (`/adminpayments/health`)
- [ ] Implement Stripe reconciliation job
- [ ] Add performance monitoring (slow query detection)
- [ ] Set up scheduled cron jobs for reconciliation

---

## 9. Testing

### Manual Testing
```bash
# Run all reconciliation jobs
python backend/scripts/reconcile_ledgers_job.py
python backend/scripts/reconcile_invoices_job.py
python backend/scripts/cleanup_stale_credit_holds_job.py

# Check health endpoints
curl http://localhost:8000/api/admin/health/db
curl http://localhost:8000/api/admin/health/findings
curl http://localhost:8000/api/admin/health/errors/summary
```

### Integration Tests (TODO)
- Test error deduplication
- Test reconciliation logic with known mismatches
- Test hold cleanup with stuck holds
- Test trace context propagation

---

## 10. Rollback Notes

**Safe to rollback**: All changes are additive (new tables, new endpoints, new jobs).

**To rollback**:
1. Remove health router from `main.py`
2. Revert `SystemErrorEntry` model changes (will lose new fields)
3. Drop `ReconciliationFinding` table if needed

**Data preservation**: Existing data is unaffected. New tables can be dropped without impact.
