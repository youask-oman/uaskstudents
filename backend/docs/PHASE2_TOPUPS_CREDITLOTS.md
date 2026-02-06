# Phase 2: Credit Lots & Top-Ups

## Overview
Phase 2 strictly implements "Pay-As-You-Go" logic using `CreditLot` entities. It sits "underneath" the Phase 1 Charging logic. When Phase 1 says "Debit 5 Credits", Phase 2 decides "Which lots do these 5 credits come from?".

## Data Model Extensions

### 1. `CreditLot` (Updates)
Existing table. We enforce:
- `lot_type`: ENUM (TOPUP, GRANT, SUBSCRIPTION, MIGRATION)
- `status`: ENUM (ACTIVE, DEPLETED, EXPIRED, VOIDED)
- `external_ref`: String (for idempotency)
- Indexes on `(user_id, status, expires_at)`

### 2. `CreditLotConsumption` (New)
The audit trail linking Debits to Lots.
- `usage_ledger_id` (FK to UsageLedger from Phase 1/0? Actually Phase 1 doesn't strictly have UsageLedger ID in API return, but it exists in DB. Linking to `BillingLedger` or `request_id` is better?)
- *Correction*: The prompt asks for `usage_ledger_id` (FK). We must ensure we can retrieve it. `BillingService.finalize_transaction` creates `BillingLedger`. Does it create `UsageLedger`? Yes, via `credit_wallet_service.deduct_credits`. We need `deduct_credits` to return the `UsageLedger` ID or object.
- Fields: `id`, `credit_lot_id`, `usage_ledger_id`, `amount`, `direction` (DEBIT/REFUND).

### 3. `TopUpProduct` (New)
Catalog of credit bundles.
- `code`, `credits`, `price_usd`, `active`.

## Logic: FIFO Consumption
Implemented in `CreditLotAllocator`.
Algorithm:
1. `deduct_credits(user_id, amount, ...)` called.
2. Fetch locks/lots: `SELECT * FROM creditlot WHERE user_id=... AND status='ACTIVE' ORDER BY expires_at ASC, purchased_at ASC`.
3. Iterate and consume.
4. If `amount` > `total_available`: Fail (or allow negative if policy says so? Phase 1 check should prevent this).
5. For each lot used:
   - Decrement `credits_remaining`.
   - If 0, set status `DEPLETED`.
   - Insert `CreditLotConsumption`.
6. Update `Subscription.credits_balance = Subscription.credits_balance - amount`. (Keep sync).

## Logic: Top-Up
1. User selects `TopUpProduct`.
2. `TopUpService.purchase(...)` called.
3. Validate, Create Payment (Simulated).
4. Create `CreditLot` (Type=TOPUP).
5. Create `UsageLedger` (CREDIT).
6. Update `Subscription.credits_balance`.

## Migration Strategy
- We will add columns to `CreditLot`.
- We will creation `CreditLotConsumption` and `TopUpProduct`.
- **Legacy Handling**: If a user has `credits_balance > 0` but NO lots, we should on-the-fly create a `MIGRATION` lot for the existing balance during the first debit, or via a migration script? 
- *Safe bet*: The Allocator handles "Balance without Lot" by treating it as "Unattributed Consumption" OR auto-migrates.
- *Strict*: We will run a `seed_migration_lots.py` to create MIGRATION lots for all positive balances.

## Deliverables
1. DB Migrations.
2. `TopUpService`, `CreditLotAllocator`.
3. Admin Dashboard updates.
4. Seed Scripts.
