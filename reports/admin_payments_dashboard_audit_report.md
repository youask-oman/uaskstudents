# Admin Payments Dashboard Audit Report

Date: 2026-02-10

## Summary
- Implemented production-grade admin payments backend endpoints (overview, requests, topups, reconciliation, stripe health) and fixed top-up minting to create CreditLot + BillingLedger + cached balance updates.
- Updated `/adminpayments` UI and navigation; removed legacy/demo placeholders; added error handling with `request_id`.
- Added smoke + integration tests and Playwright spec for payments navigation.

## UI / Navigation
- Admin sidebar now includes **Payments** linking to `/adminpayments`.
- `/adminpayments` tabs: Overview, Requests, Top-Ups, Legacy Subscriptions (read-only), Invoices, Stripe Events, Reconciliation, Pricing, Payments Config.
- `/adminpayments/requests` redirects to `?tab=requests` for single-source navigation.

## API Evidence (Live DEV)
**Overview**
```
GET /api/admin/payments/overview
{
  "start_date": "2026-01-11T17:04:44.885998",
  "days": 30,
  "metrics": {
    "provider_cost_usd": 0,
    "credits_consumed": 0.0,
    "credits_minted": 0.0,
    "stripe_revenue_gross_usd": 0,
    "refunds_total_usd": 0,
    "successful_payments": 0,
    "failed_payments": 0,
    "request_count": 0,
    "total_tokens": 0,
    "outstanding_hold_credits": 0
  }
}
```

**Stripe Health**
```
GET /api/admin/payments/stripe/health
{
  "ok": false,
  "mode": "unknown",
  "account_id": null,
  "api_version": null,
  "last_error": "Invalid API Key provided: 1233"
}
```

**Top-Ups**
```
GET /api/admin/payments/topups?page=1&page_size=5
{
  "total": 2,
  "page": 1,
  "page_size": 5,
  "data": [
    {
      "id": 2,
      "created_at": "2026-02-10T17:07:42.043586",
      "user_id": 1,
      "user_email": "admin@uask.ai",
      "status": "FULFILLED",
      "credits": 550.0,
      "price_usd": 5.0,
      "currency": "USD",
      "product_code": "topup_5",
      "product_name": "$5 Pack",
      "stripe_payment_intent_id": "manual_topup_test_2",
      "stripe_checkout_session_id": null,
      "credit_lot_id": 14,
      "ledger_id": 3
    }
  ]
}
```

## DB Proof (Manual Top-Up)
```
credit_lot: {
  id: 14,
  lot_type: "TOPUP",
  credits_total: 550.0,
  external_ref: "manual_topup_test_2",
  amount_paid: 5.0
}

billing_ledger: {
  id: 3,
  action_type: "TOPUP",
  request_id: "manual_topup_test_2",
  delta_credits: 550.0,
  credits_before: 1550.0,
  credits_after: 2100.0
}
```

## Tests
**Executed**
- `python -m pytest backend/tests/smoke/test_admin_payments_routes.py -q`
  - Result: `2 passed`

**Added (not run in this session)**
- `backend/tests/smoke/test_admin_payments_topup_integration.py`
- `backend/tests/smoke/test_admin_payments_reconciliation.py`
- `tests/e2e/admin_payments_nav.spec.ts` (screenshots to `reports/screenshots/payments/`)

## Notes / Gaps
- Stripe health reports invalid key in DEV; set valid `STRIPE_SECRET_KEY` to enable live/test verification.
- Existing historical top-up order `manual_topup_test_1` was created before ledger linkage update; newer orders now link `credit_lot_id` + `ledger_id`.

## Next Steps
- Run Playwright spec for screenshots: `npx playwright test tests/e2e/admin_payments_nav.spec.ts`.
- Run the added smoke/integration tests for full proof.
- Set valid Stripe keys in `.env` for DEV/PROD health checks.
