# Frontend ? Backend Alignment (v1)

This document updates frontend integration to match backend contracts in `reports/backend_frontend_contract_v1.md` **after** STOP SHIP fixes.

**Date**: 2026-02-10

---

## Status: STOP SHIP Closed (Backend Patches Applied)

Closed items:
1. Solve idempotency_key added to `SolveRequest` and enforced in `/api/v1/solve_v3_stream` (idempotent replay returns same attempt/request).
2. Canonical tier enum accepted: `three_step`, `short`, `standard`, `research` (external). Internally mapped to FREE/SHORT/STANDARD/RESEARCH for prompt binding.
3. Global error wrapper standardized (`error.code`, `error.message`, `error.request_id`, `error.details`), `detail` preserved for backward compatibility.
4. Pricing version exposure standardized:
   - `/api/v1/credits/estimate` returns `pricing_version_plan` and `pricing_version_token_config`.
   - Solve telemetry includes `pricing_version_plan` and `config_version_id`.
5. Wallet computed balance should be displayed as authoritative (`computed_balance`).

---

## Canonical Enums

**Tier enum (frontend ? backend)**
- `three_step`
- `short`
- `standard`
- `research`

**Solve requested_mode**
- `minimal`
- `detailed`

**Input modality**
- `text`
- `ocr_image`
- `ocr_pdf`
- `voice`

---

## 1) Credits Estimate (Pricing Preview)

**Endpoint**: `POST /api/v1/credits/estimate`

**Request**
```json
{
  "tier": "three_step|short|standard|research",
  "input_type": "text|ocr_image|ocr_pdf|voice",
  "asset_type": "none|image|pdf",
  "question_count": 1,
  "addons": {
    "ocr": false,
    "voice": false,
    "verify": false,
    "plot": false
  },
  "graph_mode": "off|auto|on"
}
```

**Response**
```json
{
  "total_credits": 10,
  "per_question_credits": 10,
  "breakdown": { "base": 10, "reason": "solve.standard.flat", "addons": {} },
  "cap_checks": { "daily_ok": true, "ocr_ok": true, "voice_ok": true },
  "pricing_version": "1",
  "pricing_version_plan": "1",
  "pricing_version_token_config": 12
}
```

**Notes**
- Estimate is **not authoritative**. Backend charges are enforced by billing/ledger.
- Frontend should display `pricing_version_plan` + `pricing_version_token_config` for cache invalidation.

---

## 2) Solve (Streaming)

**Endpoint**: `POST /api/v1/solve_v3_stream?user_id={id}`

**Request (SolveRequest)**
```json
{
  "confirmed_text": "Solve x^2 - 5x + 6 = 0",
  "tier": "standard",
  "requested_mode": "detailed",
  "input_modality": "text",
  "graph_mode": "auto",
  "features_used": {
    "ocr_used": false,
    "voice_used": false,
    "plot_requested": true
  },
  "idempotency_key": "uuid-string",
  "trusted_context": {
    "learning_mode": "solve",
    "grade_level": "10"
  }
}
```

**SSE Events**
- `meta` ? includes `attempt_id`, `request_id`, `tier_effective`, prompt/schema IDs, pricing versions.
- `stage` ? progress text.
- `delta` ? text stream chunks.
- `telemetry` ? tokens, model, latency.
- `done` ? `{ ok: true|false, session_id? }`

**Meta Example**
```json
{
  "request_id": "<uuid>",
  "attempt_id": "<uuid>",
  "tier_requested": "standard",
  "effective_tier": "standard",
  "pricing_version_plan": "1",
  "config_version_id": 12,
  "prompt_binding_id": "...",
  "output_schema_id": "..."
}
```

**Done Example (success)**
```json
{ "type": "done", "ok": true, "session_id": 123, "message_id": 456 }
```

**Done Example (failure)**
```json
{
  "type": "done",
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "Schema validation failed",
    "request_id": "<uuid>"
  }
}
```

**Idempotency**
- Always send `idempotency_key`.
- Second request with same key returns same `attempt_id`/`request_id` and does **not** double-charge.

**Resume**
- `GET /api/v1/attempt/{attempt_id}`
- `GET /api/v1/attempt/{attempt_id}/events`

---

## 3) Wallet (Student)

**Endpoints**
- `GET /api/v1/wallet/summary` ? show `computed_balance` as primary.
- `GET /api/v1/wallet/lots`
- `GET /api/v1/wallet/ledger`
- `GET /api/v1/wallet/programs`

**UI Rule**: Use `computed_balance` for display and gating. Show `cached_balance` only in admin/debug.

---

## 4) Top-ups

**Endpoints**
- `GET /api/v1/topups/products`
- `POST /api/v1/topups/stripe/checkout`

**Flow**
1. Fetch packs from `/topups/products`.
2. Start checkout via `/topups/stripe/checkout`.
3. On Stripe success, webhook mints `CreditLot TOPUP`.
4. Frontend refreshes wallet summary/ledger.

---

## 5) Admin Payments Dashboard

Use `/api/admin/payments/*` endpoints:
- `overview`, `requests`, `topups`, `invoices`, `stripe/health`, `stripe/events`, `reconciliation`, `pricing`, `config`.

---

## 6) Legacy Subscriptions UI

- Treat subscriptions as **Legacy (Read Only)**.
- Do not show any purchase flows for subscriptions.

---

## Checklist for Frontend Devs

1. Update tier selector to use `three_step|short|standard|research`.
2. Update credits estimate call to `POST /api/v1/credits/estimate` with canonical enums.
3. Update solve request to include `idempotency_key` (required).
4. Update SSE parser to read `pricing_version_plan` and `config_version_id` from `meta`.
5. Update wallet views to display `computed_balance` and label cached balance as debug.
6. Update top-up UI to fetch packs from `/api/v1/topups/products`.
7. Ensure admin payments dashboard uses `/api/admin/payments/*` endpoints only.
8. Remove or mark subscription purchase UI as Legacy / Read Only.

---

## Test Plan (Required)

**Playwright (frontend)**
- Tier selection across all tiers (including three_step + short)
- Solve flow: ensure SSE `meta`, `telemetry`, `done` received
- Wallet balance decreases by backend-charged credits
- Failure path: error shows `error.code` + `error.request_id`
- Double-click solve: idempotency_key prevents double charge

**Backend smoke**
- `/api/v1/credits/estimate` works for all tiers
- `/api/v1/solve_v3_stream` accepts idempotency_key and dedupes
- wallet endpoints return computed balance
- top-up webhook ? CreditLot TOPUP created
