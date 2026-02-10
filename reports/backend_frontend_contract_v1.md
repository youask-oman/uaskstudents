# Backend Billing & Solve Contract Report (v1)

Generated from code in `backend/app` and related services. This report is tied to concrete source locations and the current runtime behavior. All paths below are workspace-relative.

**Date**: 2026-02-10

---

## 1) Endpoint Inventory (Canonical)

Notes:
- All `/api/v1/*` routes come from `backend/app/api.py` (router included in `backend/app/main.py`).
- Billing admin routes are in `backend/app/admin_billing/*` and `backend/app/api_admin_payments*.py`.
- Auth: `get_current_user` in `backend/app/api.py` (JWT), admin roles in `backend/app/api_admin.py` and `backend/app/admin_billing/deps.py`.

### Solve & Attempts

| Method | Path | Auth | Request (high-level) | Response (high-level) | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/solve` | user | `SolveRequest` fields (`text_query`, `confirmed_text`, `tier`, `requested_mode`, `features_used`, `graph_mode`, `input_modality`, etc.) | `SolveResponse` (`session_id`, `solution`, `telemetry`, `solve_session_id`) | `backend/app/api.py:3774` | Non-streamed solve (legacy v1 response). |
| POST | `/api/v1/solve_v3_stream?user_id=...` | user | `SolveRequest` JSON body (same model) | SSE: `meta`, `stage`, `delta`, `telemetry`, `done` events | `backend/app/api.py:5113` | Streaming solve. Generates `request_id` + `attempt_id` internally. |
| POST | `/api/v1/solve/clarify` | user | `{ attempt_id, user_id, user_response }` | `SolveResponse`-like payload with status | `backend/app/api.py:10226` | Clarifier for ambiguous responses. |
| GET | `/api/v1/attempt/{attempt_id}` | user | n/a | `{ attempt_id, request_id, status, failure_code, error_message, clarification_count, created_at, updated_at }` | `backend/app/api.py:10337` | Used to resume attempts. |
| GET | `/api/v1/attempt/{attempt_id}/events` | user | n/a | SSE events from Redis | `backend/app/api.py:10366` | Event stream for pipeline UI. |

### Public / Pricing Config (Tier + Credits)

| Method | Path | Auth | Request | Response | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/credits/estimate` | none or user | `CreditsEstimateRequest` | `CreditsEstimateResponse` | `backend/app/bg_routers/credits_router.py:108` | Primary pricing estimate for frontend. Uses Plan multipliers. |
| GET | `/api/v1/public/plans` | none | n/a | list of `Plan` | `backend/app/api.py:9455` | Public plan list (legacy subscription pricing). |

### User Wallet (Student)

| Method | Path | Auth | Request | Response | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/wallet/summary` | user | n/a | `WalletSummaryResponse` | `backend/app/api_wallet.py:63` | Includes computed vs cached balance. |
| GET | `/api/v1/wallet/lots` | user | `limit`, `offset` | `PaginatedResponse<WalletLotResponse>` | `backend/app/api_wallet.py:98` | Credit lots. |
| GET | `/api/v1/wallet/ledger` | user | `limit`, `offset` | `PaginatedResponse<WalletLedgerEntryResponse>` | `backend/app/api_wallet.py:140` | Billing ledger entries. |
| GET | `/api/v1/wallet/programs` | user | `limit`, `offset` | `PaginatedResponse<WalletProgramEnrollmentResponse>` | `backend/app/api_wallet.py:188` | Active program enrollments. |

### Top-ups (User)

| Method | Path | Auth | Request | Response | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/topups/products` | none | n/a | `List<TopUpProductRead>` | `backend/app/api_topups.py:63` | Pack list for checkout. |
| POST | `/api/v1/topups/checkout` | user | `{ product_code }` | `{ checkout_url, payment_intent_id }` | `backend/app/api_topups.py:81` | Mock checkout. |
| POST | `/api/v1/topups/stripe/checkout` | user | `{ product_code, success_url, cancel_url }` | Stripe session payload | `backend/app/api_topups.py:93` | Real Stripe checkout session. |
| POST | `/api/v1/topups/confirm` | user | `{ product_code, external_ref, user_id }` | `{ status, lot_id, credits_added, new_balance }` | `backend/app/api_topups.py:112` | Manual confirmation (idempotent by `external_ref`). |

### Admin Billing (Programs, Wallet, Holds, Refunds, Packs, Pricing)

| Method | Path | Auth | Request | Response | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/admin/billing/programs` | admin | `status, limit, offset` | `PaginatedResponse<ProgramResponse>` | `backend/app/admin_billing/billing_programs.py:112` | Credit program definitions. |
| POST | `/api/admin/billing/programs` | superadmin | `CreateProgramRequest` | `ProgramResponse` | `backend/app/admin_billing/billing_programs.py:160` | Audited. |
| PUT | `/api/admin/billing/programs/{id}` | superadmin | `UpdateProgramRequest` | `ProgramResponse` | `backend/app/admin_billing/billing_programs.py:241` | Audited. |
| POST | `/api/admin/billing/programs/enroll` | superadmin | `EnrollUserRequest` | `EnrollmentResponse` | `backend/app/admin_billing/billing_programs.py` | Enroll user. |
| POST | `/api/admin/billing/programs/unenroll` | superadmin | `UnenrollUserRequest` | `EnrollmentResponse` | `backend/app/admin_billing/billing_programs.py` | Unenroll user. |
| GET | `/api/admin/billing/users/{user_id}/summary` | admin | n/a | `WalletSummary` | `backend/app/admin_billing/billing_wallet.py` | Wallet summary. |
| GET | `/api/admin/billing/users/{user_id}/lots` | admin | `limit, offset` | `PaginatedResponse<CreditLotResponse>` | `backend/app/admin_billing/billing_wallet.py` | Credit lots. |
| GET | `/api/admin/billing/users/{user_id}/ledger` | admin | `limit, offset` | `PaginatedResponse<LedgerEntryResponse>` | `backend/app/admin_billing/billing_wallet.py` | Billing ledger. |
| POST | `/api/admin/billing/users/{user_id}/grant` | superadmin | `GrantCreditsRequest` | `WalletMutationResponse` | `backend/app/admin_billing/billing_wallet.py` | Grants credits. |
| POST | `/api/admin/billing/users/{user_id}/refund` | superadmin | `RefundCreditsRequest` | `WalletMutationResponse` | `backend/app/admin_billing/billing_wallet.py` | Refunds credits. |
| POST | `/api/admin/billing/users/{user_id}/reconcile` | admin | `ReconcileRequest` | `WalletMutationResponse` | `backend/app/admin_billing/billing_wallet.py` | Recompute cached balance. |
| GET | `/api/admin/billing/holds` | admin | filters | list holds | `backend/app/admin_billing/billing_holds.py` | Holds list. |
| POST | `/api/admin/billing/holds/{hold_id}/release` | superadmin | `{ reason, idempotency_key }` | hold | `backend/app/admin_billing/billing_holds.py` | Force release hold. |
| GET | `/api/admin/billing/refunds` | admin | filters | list refunds | `backend/app/admin_billing/billing_refunds.py` | Refund list. |
| POST | `/api/admin/billing/refunds` | superadmin | `RefundRequest` | refund | `backend/app/admin_billing/billing_refunds.py` | Audited. |
| GET | `/api/admin/billing/packs` | admin | filters | list packs | `backend/app/admin_billing/billing_packs.py` | Top-up packs. |
| POST | `/api/admin/billing/packs` | superadmin | pack create | pack | `backend/app/admin_billing/billing_packs.py` | Audited. |
| PUT | `/api/admin/billing/packs/{id}` | superadmin | pack update | pack | `backend/app/admin_billing/billing_packs.py` | Audited. |
| DELETE | `/api/admin/billing/packs/{id}` | superadmin | `{ reason }` | pack | `backend/app/admin_billing/billing_packs.py` | Audited. |
| GET | `/api/admin/billing/pricing` | admin | `provider, model` | `{ pricing: [...] }` | `backend/app/admin_billing/billing_pricing.py` | Provider pricing (alias). |
| POST | `/api/admin/billing/pricing` | admin | `PricingPayload` | `ProviderModelPricing` | `backend/app/admin_billing/billing_pricing.py` | Creates pricing. |
| DELETE | `/api/admin/billing/pricing/{id}` | admin | `{ reason }` | retired pricing | `backend/app/admin_billing/billing_pricing.py` | Retire pricing. |
| GET | `/api/admin/billing/health/*` | admin | n/a | billing health responses | `backend/app/admin_billing/billing_health.py` | Diagnostics. |

### Payments Dashboard (Admin)

| Method | Path | Auth | Request | Response | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/admin/payments/overview` | staff | `range_days` | `{ start_date, days, metrics }` | `backend/app/api_admin_payments.py:43` | Overview metrics. |
| GET | `/api/admin/payments/requests` | staff | `page, page_size, status, user_id` | `{ total, data, page, page_size }` | `backend/app/api_admin_payments.py:150` | TopUpOrder list. |
| GET | `/api/admin/payments/topups` | staff | `page, page_size, search` | `{ total, data, page, page_size }` | `backend/app/api_admin_payments.py:71` | Top-up list. |
| GET | `/api/admin/payments/topups/{id}` | staff | n/a | `{ topup, payment, credit_lot }` | `backend/app/api_admin_payments.py:118` | Top-up detail. |
| GET | `/api/admin/payments/subscriptions` | staff | `page, page_size, status` | `{ total, data, page, page_size }` | `backend/app/api_admin_payments.py:197` | Legacy subscriptions. |
| GET | `/api/admin/payments/invoices` | staff | `page, page_size, user_id, kind, status` | `{ total, data, page, page_size }` | `backend/app/api_admin_payments.py:332` | Invoices list. |
| GET | `/api/admin/payments/invoices/{id}` | staff | n/a | `{ invoice, lines }` | `backend/app/api_admin_payments.py:354` | Invoice detail. |
| GET | `/api/admin/payments/invoices/{id}/html` | staff | n/a | HTML | `backend/app/api_admin_payments.py:369` | Invoice HTML render. |
| GET | `/api/admin/payments/stripe/health` | staff | n/a | `{ ok, mode, account_id, api_version, last_error }` | `backend/app/api_admin_payments.py:246` | Stripe health. |
| GET | `/api/admin/payments/stripe/events` | staff | `page, page_size, event_type, status` | `{ total, data, page, page_size }` | `backend/app/api_admin_payments.py:271` | Stripe events. |
| POST | `/api/admin/payments/stripe/events/{id}/replay` | admin | n/a | `{ status, process_status }` | `backend/app/api_admin_payments.py:292` | Replay webhook event. |
| GET | `/api/admin/payments/reconciliation` | staff | n/a | `ReconciliationReport` | `backend/app/api_admin_payments.py:317` | Dry-run reconciliation. |
| POST | `/api/admin/payments/reconciliation/run` | superadmin | `{ confirm, reason }` | `{ status, message, confirm }` | `backend/app/api_admin_payments.py:356` | Requires confirm string. |
| GET | `/api/admin/payments/config` | admin | n/a | `{ config, history }` | `backend/app/api_admin_payments_config.py:26` | Payments config. |
| PUT | `/api/admin/payments/config` | admin | `{ config, reason }` | `{ status, version }` | `backend/app/api_admin_payments_config.py:74` | Update config. |
| GET | `/api/admin/payments/pricing` | admin | n/a | `{ provider_pricing, topup_packs, stripe_price_map }` | `backend/app/api_admin_payments_config.py:100` | Combined pricing view. |
| POST | `/api/admin/payments/pricing` | superadmin | `{ kind, action, data, reason, idempotency_key }` | object | `backend/app/api_admin_payments_config.py:131` | CRUD top-up packs + Stripe price map. |
| GET | `/api/admin/payments/pricing/provider` | admin | `provider, model` | `{ pricing }` | `backend/app/api_admin_payments_config.py:278` | Provider pricing list. |
| POST | `/api/admin/payments/pricing/provider` | admin | `ProviderModelPricing` + `reason` | `ProviderModelPricing` | `backend/app/api_admin_payments_config.py:335` | Create pricing. |
| PUT | `/api/admin/payments/pricing/provider/{id}` | admin | `{ updates, reason }` | `ProviderModelPricing` | `backend/app/api_admin_payments_config.py:422` | Update future pricing. |
| DELETE | `/api/admin/payments/pricing/provider/{id}` | admin | `{ reason }` | `ProviderModelPricing` | `backend/app/api_admin_payments_config.py:463` | Retire pricing. |

---

## 2) Solve Request/Response Contract (Concrete)

### 2.1 SolveRequest model (used by `/api/v1/solve` and `/api/v1/solve_v3_stream`)

Source: `backend/app/api.py:648`.

**Fields accepted**:
- `image_url?: string`
- `text_query?: string`
- `confirmed_markdown?: string`
- `confirmed_text?: string`
- `confirmed_latex_blocks?: list<object>`
- `artifact_id?: number`
- `question_id?: number`
- `problem_hash?: string`
- `subject?: string`
- `difficulty?: string`
- `mode?: string` (default `"general"`)
- `user_id?: number`
- `is_make_it_right?: boolean` (default `false`)
- `previous_request_id?: string`
- `has_voice?: boolean` (default `false`)
- `tier?: string` (description: free|standard|research)
- `trusted_context?: object`
- `requested_mode?: string` (default `"minimal"`)
- `features_used?: object`
- `input_modality?: string` (`text`, `ocr_image`, `ocr_pdf`, `voice`)
- `token_policy?: string`
- `verification_level?: string` (`light|moderate|strict`)
- `include_graph?: boolean` (default `false`)
- `graph_mode?: string` (`off|auto|on`)
- `attach_to_step_id?: number`
- `force_validity?: boolean` (default `false`)

### 2.2 `/api/v1/solve` response (SolveResponse)

Source: `backend/app/api.py:688`.

```json
{
  "session_id": 123,
  "solution": {
    "problem": { "goal": "Solve", "statement": "sqrt(x+5) = x - 1" },
    "steps": [{ "index": 1, "title": "Isolate root", "work": "..." }],
    "final_answer": { "answer_text": "x = 3" }
  },
  "concepts": [],
  "visuals": [],
  "model_used": "gpt-5-mini",
  "tokens_used": 512,
  "has_image": false,
  "telemetry": {
    "provider": "openai",
    "model": "gpt-5-mini",
    "latency_ms_total": 8421,
    "token_usage": {
      "input_tokens": 120,
      "output_tokens": 392,
      "total_tokens": 512,
      "cached_tokens": 0
    }
  },
  "solve_session_id": 456
}
```

### 2.3 `/api/v1/solve_v3_stream` SSE contract

Source: `backend/app/api.py:5113` and SSE event writers at ~`backend/app/api.py:5579+`.

**Event sequence**: `meta` -> `stage` -> multiple `delta` -> `telemetry` -> `done`.

**Meta event** (example):
```json
{
  "request_id": "2b9b7a3d-1f39-4e2b-9b1a-9b2d1d9f2f4a",
  "attempt_id": "f0f7a3ad-4f6f-49ad-9a92-0a1a0b2f9a33",
  "provider": "openai",
  "model": "gpt-5-mini",
  "tier_requested": "free",
  "effective_tier": "free",
  "mode": "minimal",
  "prompt_binding_id": "binding_123",
  "global_system_prompt_id": "system_abc",
  "developer_prompt_id": "dev_xyz",
  "output_schema_id": "schema_001",
  "prompt_versions": { "system": 12, "developer": 3, "schema": 5 }
}
```

**Stage event**:
```json
{ "type": "stage", "name": "Calling AI model...", "at_ms": 1034 }
```

**Delta event**:
```json
{ "type": "delta", "text": "Step 1: ..." }
```

**Telemetry event**:
```json
{
  "provider": "openai",
  "model": "gpt-5-mini",
  "total_tokens": 512,
  "latency_ms_openai": 7312,
  "truncated": false
}
```

**Done event (success)**:
```json
{ "type": "done", "ok": true, "session_id": 123, "message_id": 999 }
```

**Done event (error)**:
```json
{
  "type": "done",
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "Schema validation failed",
    "validation_errors": ["..."],
    "request_id": "2b9b7a3d-1f39-4e2b-9b1a-9b2d1d9f2f4a"
  }
}
```

### 2.4 Tier-specific examples (frontend-requested)

These are **request examples** matching the SolveRequest schema. Use `confirmed_text` for frontend input. The backend accepts `tier` values as strings; `requested_mode` controls output length and is used in solver routing.

**three_step (Free UI)**
```json
{
  "confirmed_text": "Solve 2x + 3 = 11",
  "tier": "free",
  "requested_mode": "minimal",
  "input_modality": "text",
  "graph_mode": "auto",
  "features_used": { "ocr_used": false, "voice_used": false, "plot_requested": false },
  "trusted_context": { "learning_mode": "solve", "grade_level": "10" }
}
```

**short**
```json
{
  "confirmed_text": "Factor x^2 - 5x + 6",
  "tier": "short",
  "requested_mode": "minimal",
  "input_modality": "text",
  "graph_mode": "auto",
  "features_used": { "ocr_used": false, "voice_used": false, "plot_requested": false },
  "trusted_context": { "learning_mode": "solve" }
}
```

**standard**
```json
{
  "confirmed_text": "Solve sqrt(x+5) = x - 1",
  "tier": "standard",
  "requested_mode": "detailed",
  "input_modality": "text",
  "graph_mode": "auto",
  "features_used": { "ocr_used": false, "voice_used": false, "plot_requested": true },
  "trusted_context": { "learning_mode": "solve", "region_country": "US" }
}
```

**research**
```json
{
  "confirmed_text": "Prove that the sequence converges and find its limit",
  "tier": "research",
  "requested_mode": "detailed",
  "input_modality": "text",
  "graph_mode": "off",
  "verification_level": "strict",
  "features_used": { "ocr_used": false, "voice_used": false, "plot_requested": false },
  "trusted_context": { "learning_mode": "solve" }
}
```

### 2.5 Failure examples (from global error handling)

Global error handlers live in `backend/app/main.py`.

**Insufficient credits** (thrown in `BillingService.initiate_hold` or `SubscriptionService.check_entitlement_and_debit`)
```json
{ "detail": "Insufficient credits" }
```
Status: `402` or `400` depending on call site.

**Validation error** (Pydantic)
```json
{ "detail": [ { "loc": ["body","confirmed_text"], "msg": "field required", "type": "value_error.missing" } ] }
```
Status: `422`.

**Upstream model timeout/incomplete**
```json
{ "detail": "Internal Server Error", "request_id": "<uuid>" }
```
Status: `500`.

**Not found**
```json
{ "detail": "Attempt not found" }
```
Status: `404`.

---

## 3) Pricing Config Contract (Tiers + Packs + Versioning)

### 3.1 Tier Credits (Plan multipliers)

- **Storage**: `Plan.multipliers` JSON (DB) parsed by `PlanMultipliers` in `backend/app/schemas/pricing.py`.
- **Schema**: `PlanMultipliers -> CreditsConfig -> SolveCreditsConfig`.
- **Location**: `backend/app/schemas/pricing.py` and `backend/app/services/subscription_service.py`.

Default **plan** tier credits (from `SubscriptionService.ensure_plans_exist`):
- `free`: text 1, snap_image 2, snap_pdf 3, voice 2
- `standard`: text 2, snap_image 3, snap_pdf 4, voice 3
- `research`: text 4, snap_image 5, snap_pdf 6, voice 5

Note: the schema includes a `short` tier (`SolveCreditsConfig.short`) but **default plan creation does not populate `short`**. See `backend/app/schemas/pricing.py` and `backend/app/services/subscription_service.py`.

### 3.2 Token-based pricing (Billing V2)

- **Storage**: `SystemConfigVersion` / `SystemConfig` with `config_type="pricing"`.
- **Schema**: `PricingConfig` in `backend/app/services/pricing_service.py`.
- **Versioning**: `SystemConfigVersion.version` (stored as `config_version_id` in BillingLedger). See `PricingService.get_pricing_config()`.

### 3.3 Top-up Packs

- **Storage**: `TopUpProduct` (DB).
- **Admin CRUD**: `/api/admin/billing/packs` (`backend/app/admin_billing/billing_packs.py`) and `/api/admin/payments/pricing` (combined view).
- **User list**: `/api/v1/topups/products` (`backend/app/api_topups.py`).

Default packs (seeded in `backend/scripts/seed_production.py`):
- `topup_5`: $5 ? 550 credits
- `topup_10`: $10 ? 1200 credits
- `topup_25`: $25 ? 3250 credits
- `topup_50`: $50 ? 7000 credits

### 3.4 Stripe price mapping

- **Storage**: `StripePriceMap` (DB, `backend/app/models/__init__.py`).
- **Admin CRUD**: `/api/admin/payments/pricing` (kind = `STRIPE_PRICE_MAP`).
- **Lookup**: `StripeService.get_price_id()` in `backend/app/services/stripe_service.py`.

### 3.5 Pack ? Stripe mapping

- `TopUpProduct.code` (e.g. `topup_10`) maps to `StripePriceMap.internal_code` (same string). See `backend/app/services/stripe_service.py` and `backend/app/api_admin_payments_config.py`.

### 3.6 Versioning contract for frontend cache

- **Credits estimate** returns `pricing_version` from `PlanMultipliers.version` (`backend/app/bg_routers/credits_router.py`).
- **Token pricing** returns `config_version_id` stored in `BillingLedger` (V2 path). Frontend should cache by version and invalidate on change.

---

## 4) Billing Write Path (DB Truth)

Tables (core):
- `CreditLot`, `CreditLotConsumption`, `BillingLedger`, `CreditHold`, `Payment`, `TopUpOrder`, `Invoice`, `InvoiceLineItem`, `UsageLedger`.
- Models in `backend/app/models/__init__.py`.

### A) Successful solve (V2 hold + settle)

**Source**: `backend/app/services/billing_service.py`.

1. Hold created: `CreditHold` via `BillingService.initiate_hold()`.
2. On completion: `BillingService.finalize_transaction()`:
- Reads `RequestEvent` for telemetry (created in solve flow).
- Computes charge using `PricingService` + `CreditEconomics`.
- Writes `BillingLedger` with `status=CHARGED` and `credits_charged`.
- Deducts credits in wallet via `CreditWalletService.deduct_credits()` which:
  - Updates `UsageLedger` (DEBIT)
  - Updates `Subscription.credits_balance` cache
  - Creates `CreditLotConsumption` entries (FIFO)
- Releases `CreditHold` (`status=released`).

**Tables touched**: `CreditHold`, `BillingLedger`, `RequestEvent`, `UsageLedger`, `CreditLotConsumption`, `Subscription`, `User` (cached balance via subscription).

### B) Failed solve

**Source**: `BillingService.fail_transaction()`

- Refunds estimated credits via `CreditWalletService.add_credits()`.
- Marks `BillingLedger.status=FAILED_REFUNDED`.

**Tables**: `BillingLedger`, `CreditLot`, `UsageLedger`, `Subscription`.

### C) Refund

**Source**: `backend/app/admin_billing/billing_wallet.py` and `backend/app/admin_billing/billing_refunds.py`.

- Creates `CreditLot` with `lot_type="REFUND"` and `source_payment_id` or `source_attempt_id`.
- Writes `BillingLedger` with `action_type="REFUND"`.
- Writes `AdminAuditLog` (all admin mutations are audited).

### D) Top-up (Stripe)

**Sources**:
- `backend/app/services/stripe_webhook_processor.py` (`fulfill_topup`).
- `backend/app/services/top_up_service.py` (`confirm_topup`).

Writes:
- `Payment` row for Stripe PaymentIntent.
- `CreditLot` with `lot_type="TOPUP"` and `external_ref`/`source_payment_id`.
- `BillingLedger` entry with `action_type="TOPUP"` and `request_id` = PaymentIntent id.
- `UsageLedger` credit entry and `Subscription.credits_balance` update.
- `TopUpOrder.fulfill_credit_lot_id` and `TopUpOrder.fulfill_usage_ledger_id` set.
- `Invoice` + `InvoiceLineItem` for receipt (best-effort).

### E) Reconciliation

**Source**: `backend/app/jobs/nightly_reconciliation.py` and `backend/app/api_admin_payments.py`.

- Computes true balance from `CreditLot` minus `CreditHold` (no reliance on `User.credits_balance`).
- If `RECONCILIATION_AUTOFIX_ENABLED` is true, updates cached `User.credits_balance`.

---

## 5) RBAC / Role-based Billing Logic

**Roles** (User model): `student`, `admin`, `employee`, `superadmin` (`backend/app/models/__init__.py`).

**Billing exemptions**:
- No explicit admin or internal bypass found in billing/solve flow.
- Billing V2 rollout can be forced for specific admin IDs via `BILLING_V2_ADMIN_IDS` (`backend/app/services/billing_feature_flags.py`).
- Credit programs entitlements can grant access to higher tiers (`allow_research_tier`, etc.) in `CreditProgramService.get_user_entitlements()`.

**Answer to required questions**:
- Are admins charged? **Yes, unless their plan or credits allow free usage.** No explicit bypass.
- If no charge: backend returns `credits_charged=0` when not billable or `VOIDED` in `BillingLedger` (V2 finalize path) and still logs telemetry.
- Env flags: `BILLING_V2_ENABLED`, `BILLING_V2_ADMIN_IDS`, `CREDIT_PROGRAMS_ENABLED`, `REFUND_V2_ENABLED`, `RECONCILIATION_AUTOFIX_ENABLED` (`backend/app/services/billing_feature_flags.py`).

---

## 6) Idempotency & Double-charge Prevention

**Ledger idempotency**:
- `BillingLedger.request_id` is used as idempotency key in `BillingService.create_pending_transaction()` and `BillingService.finalize_transaction()`.

**Hold idempotency**:
- `CreditHold.request_id` used to prevent duplicate holds (`BillingService.initiate_hold`).

**Top-up idempotency**:
- `TopUpOrder.stripe_payment_intent_id` is unique (DB index), and webhook fulfillment checks existing `Payment` and `CreditLot` by `external_id`/`external_ref` (`stripe_webhook_processor.fulfill_topup`).

**Credit program grants**:
- `CreditProgramGrantLog` enforces (user_id, program_id, month) idempotency (`CreditProgramService.grant_monthly_credits`).

**Admin mutations**:
- Many requests include `idempotency_key` and are stored in `AdminAuditLog` (`backend/app/models/admin_audit_log.py` and `backend/app/services/audit_log_service.py`).

---

## 7) Error Contract (Canonical)

Global error handlers are in `backend/app/main.py`.

**HTTPException**
```json
{ "detail": "<string or object>" }
```
Status: as raised.

**Validation error**
```json
{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }
```
Status: `422`.

**Unhandled exception**
```json
{ "detail": "Internal Server Error", "request_id": "<uuid or null>" }
```
Status: `500`.

**Headers**
- `X-Request-ID` is echoed when provided (middleware in `backend/app/main.py`).
- `X-Trace-ID` always present.

**Note**: There is no single `error_code` enum in the global handler. Individual endpoints may include `error_code` in their own payloads, but it is not consistent.

---

## 8) Flags & Rollout (Frontend Impact)

From `backend/app/services/billing_feature_flags.py`:
- `BILLING_V2_ENABLED`: global switch for new billing flow.
- `BILLING_V2_ROLLOUT_PERCENT`: % rollout by user ID.
- `BILLING_V2_ADMIN_IDS`: force-enable for listed IDs.
- `CREDIT_PROGRAMS_ENABLED`: enables credit programs (requires V2).
- `REFUND_V2_ENABLED`: enables refund V2 semantics.
- `RECONCILIATION_AUTOFIX_ENABLED`: auto-fix cached balances.

Frontend behavior:
- If V2 disabled, expect legacy billing paths (subscription credits). Wallet remains valid but ledger semantics differ.
- If credit programs disabled, ignore program entitlements returned from `/wallet/summary` and `/wallet/programs`.

---

## 9) Tests & How To Run

Commands (copy/paste):

```bash
# Reset dev DB + seed

docker compose exec orchestrator python scripts/dev_recreate_db_and_seed.py --confirm RESET_DEV_DB

# Seeding tests

docker compose exec orchestrator pytest tests/seeding/ -q

# Smoke tests

docker compose exec orchestrator pytest tests/smoke/ -q

# Payments-specific smoke tests

docker compose exec orchestrator pytest backend/tests/smoke/test_admin_payments_routes.py -q

docker compose exec orchestrator pytest backend/tests/smoke/test_admin_payments_topup_integration.py -q

docker compose exec orchestrator pytest backend/tests/smoke/test_admin_payments_reconciliation.py -q
```

No dedicated contract verification script exists in the repo at this time.

---

## 10) Frontend TODO Checklist (Alignment Map)

- Tier selector -> `/api/v1/credits/estimate` (`tier`, `input_type`, `asset_type`, `addons`) and Plan multipliers in DB.
- Solve button -> `/api/v1/solve_v3_stream` with `confirmed_text`, `tier`, `requested_mode`, `features_used`, `graph_mode`. Track `attempt_id` from `meta` event.
- Result screen -> use `telemetry` event and `done` event fields; use `session_id` to route to `/chat/{session_id}`.
- Wallet screen -> `/api/v1/wallet/summary`, `/wallet/lots`, `/wallet/ledger`, `/wallet/programs`.
- Top-up flow -> `/api/v1/topups/products` -> `/api/v1/topups/stripe/checkout` -> webhook -> `CreditLot TOPUP`.
- Admin pricing screen -> `/api/admin/payments/pricing` and `/api/admin/payments/pricing/provider` with audit reasons.
- Payments dashboard -> `/api/admin/payments/*` endpoints for overview, requests, topups, invoices, stripe events, reconciliation.

---

## STOP SHIP (Must Fix Before Frontend Changes)

1. **Solve idempotency key not enforced**: `SolveRequest` has no `idempotency_key` field; frontend cannot prevent double-charging at the solve layer. Only ledger request_id is internal. Add `idempotency_key` to SolveRequest and enforce in hold/ledger creation.
2. **Tier mismatch (`short`)**: Frontend uses `SHORT` tier, but backend tier handling is inconsistent. `PlanMultipliers` schema includes `short`, but `SubscriptionService.ensure_plans_exist` does not populate it. `PricingService.solve_pricing` only defines `FREE/STANDARD/RESEARCH`. Resolve and document canonical tier enum.
3. **Error contract lacks `error_code`**: Global handlers return `{ detail }` only. Frontend expects `request_id` everywhere and stable `error_code`. Add consistent error wrapper or document endpoint-specific codes.
4. **Credits vs tokens pricing versions**: Credits estimate returns `pricing_version` from Plan multipliers, but V2 billing uses `SystemConfigVersion` (`config_version_id`). Frontend cache invalidation must reconcile these or backend must standardize version exposure.
5. **Admin vs user wallet balance sources**: `User.credits_balance` is cache only, but some flows still rely on `Subscription.credits_balance`. Ensure frontend uses `/wallet/summary.computed_balance` for display, not cached values.
