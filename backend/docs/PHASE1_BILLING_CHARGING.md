# Phase 1: Deterministic Billing & Charging

## Overview
Phase 1 implements the definitive "charging" logic for the billing system. Unlike Phase 0 (which was about observability and cost auditing), Phase 1 manages the actual debiting of User Credits in a strict, transactional, and idempotent manner.

## Key Changes

### 1. Data Model Updates
- **`CreditEconomics`**: Configuration for how we translate Cost (USD) -> Price (Credits). Managed via `SystemConfigVersion`.
- **`CreditHold`**: Lifecycle management for reserving credits.
- **`BillingLedger`**: Extended to support the "Finalized Transaction" concept.
- **`UsageLedger`**: Strict constraints to ensure 1 Debit per Request.

### 2. The Transaction Lifecycle
1. **Initiate (Pre-flight)**:
   - Check user balance.
   - Create `CreditHold` (State: ACTIVE).
   - If fail -> Reject Request.
2. **Execute**:
   - Run Solver / LLM.
   - Record Telemetry (`RequestEvent`, `SolverOutputAttempt`).
3. **Finalize (Post-flight)**:
   - Acquire Lock (by request_id).
   - Check Idempotency (if already charged, return).
   - Compute `provider_cost_usd` (using Phase 0 service).
   - Compute `charge_usd` and `charge_credits` (using `CreditEconomics`).
   - Create `BillingLedger` (State: CHARGED or REFUNDED).
   - Apply to `UsageLedger`:
     - If Billable: DEBIT full amount. Release remaining Hold.
     - If Refund/Void: No Debit. Release Hold.
   - Update `CreditHold` (State: RELEASED/FINALIZED).

## Schema Changes

### `BillingLedger` (Updates)
We will extend the existing `BillingLedger` table.
- **Add columns**:
  - `provider_cost_usd`: float
  - `markup_multiplier`: float
  - `charge_usd`: float
  - `credit_value_usd`: float
  - `finalized_at`: datetime (Nullable)
  - `tier`: str (Enum)
  - `event_type`: str (Enum)
- **Constraints**:
  - `request_id` must be UNIQUE (Strict 1:1 mapping).

### `UsageLedger` (Constraints)
- Add Unique Index on `(request_id, transaction_type)` where type='DEBIT'. This guarantees we never double-charge.

## Configuration: `CreditEconomics`
Stored in `SystemConfigVersion` under key `credit_economics`.
```json
{
  "credit_value_usd": 0.02,
  "tiers": {
    "FREE": {"multiplier": 1.0, "fixed_fee": 0.0},
    "STANDARD": {"multiplier": 2.0, "fixed_fee": 0.05},
    "RESEARCH": {"multiplier": 4.0, "fixed_fee": 0.10}
  },
  "minimum_charge_credits": 1,
  "rounding_policy": "CEIL"
}
```

## Migration Plan
1. **DB Migration**: Add columns to `BillingLedger` and constraints.
2. **Code**: Implement `BillingService.initiate_hold` and `BillingService.finalize_transaction`.
3. **Integration**: Switch `solver.py` / `api.py` to use `BillingService` v2 methods.
4. **Validation**: Run integration tests ensuring Reference ID uniqueness blocks double charges.

## Rollback Strategy
- The DB changes are additive (nullable columns).
- Code uses feature flags or new methods. Old methods (`create_pending_transaction`) can remain until full switch.
- If logic fails, we revert the `api.py` call to the old method.
