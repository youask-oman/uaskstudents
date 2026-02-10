# Frontend Tokens + Credits Simulated Report

Date: 2026-02-10

## Environment
- APP_ENV: DEV
- BILLING_FAKE_SOLVER_ENABLED: true
- NEXT_PUBLIC_ENABLE_DEV_TOOLS: true

## Tests Executed
- `tests/e2e/solve_tokens_credits_simulated.spec.ts`

## Test Run Result
Status: FAILED

### Failure Summary
1) Frontend not running on `http://localhost:3000`:
   - Chromium failures: `net::ERR_CONNECTION_REFUSED` on `/login`
2) Playwright browsers missing:
   - Firefox/WebKit executables not found. Requires `npx playwright install`.

### Raw Highlights
- `page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3000/login`
- `Executable doesn't exist ... ms-playwright/...` (Firefox/WebKit)

## Evidence
### Screenshots
Not generated because tests failed before page load.
Expected directory:
- `reports/screenshots/solve_simulated/`

### Sample SSE Events (Expected)
```json
{ "event": "meta", "data": { "attempt_id": "<uuid>", "request_id": "<uuid>", "tier_requested": "three_step", "tier_effective": "three_step" } }
```
```json
{ "event": "telemetry", "data": { "provider": "openai_simulated", "model": "gpt-5-mini", "input_tokens": 2000, "output_tokens": 1000, "cached_tokens": 250, "total_tokens": 3000 } }
```
```json
{ "event": "done", "data": { "ok": true, "session_id": 123, "message_id": 456 } }
```

### API Response Snippets (Expected)
- `GET /api/v1/attempt/{attempt_id}` includes `telemetry` and `billing`:
```json
{
  "attempt_id": "<uuid>",
  "request_id": "<uuid>",
  "telemetry": { "input_tokens": 2000, "output_tokens": 1000, "total_tokens": 3000 },
  "billing": { "credits_charged": 5, "credits_after": 995, "ledger_id": 123, "hold_id": 77 }
}
```

### DB Proof (DEV helper)
- `GET /api/dev/solve_debug?user_id=<id>` returns:
  - latest `BillingLedger`
  - latest `CreditHold`
  - latest `CreditLotConsumption`
  - latest `SolverOutputAttempt`

Example response shape:
```json
{
  "attempt": { "attempt_id": "<uuid>", "input_tokens": 2000 },
  "ledger": { "credits_charged": 5 },
  "hold": { "status": "finalized" },
  "consumption": [ { "amount": 5 } ]
}
```

## Expected Results (Per Tier)
- three_step: credits_charged = 5
- short: credits_charged = 7
- standard: credits_charged = 10
- research: credits_charged = 25

## Failure Scenario
- debug_force_error=true
- Expect `credits_charged = 0` and wallet unchanged
- UI shows error code + request_id

## Idempotency Scenario
- Same `idempotency_key` used twice
- Expect same `attempt_id`, no additional credit charge

## How To Run (Prereqs)
1) Start frontend on `http://localhost:3000`.
2) Install Playwright browsers:
```bash
npx playwright install
```

## How To Run (E2E)
```bash
# backend (DEV)
$env:APP_ENV="DEV"
$env:BILLING_FAKE_SOLVER_ENABLED="true"

# frontend (DEV)
$env:NEXT_PUBLIC_ENABLE_DEV_TOOLS="true"

# e2e
npm run test:e2e -- tests/e2e/solve_tokens_credits_simulated.spec.ts
```
