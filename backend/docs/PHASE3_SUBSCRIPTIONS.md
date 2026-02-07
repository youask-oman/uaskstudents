# Phase 3: Subscriptions Implementation Plan

## Overview
Phase 3 enforces subscription benefits (monthly credit grants, resets) and policies (overage handling) while maintaining compatibility with the Pay-As-You-Go (PayGo) system from Phase 2. This phase introduces `SubscriptionPeriod` tracking and leverages `CreditLot` for monthly grants to ensure a unified consumption model.

## Core Concepts

### 1. Subscription Period
A formal `SubscriptionPeriod` entity tracks the lifecycle of billing cycles.
- **Start/End**: Defines the window for usage counters and validity of granted credits.
- **Status**: OPEN (active) or CLOSED (past).
- **Granting**: Credits are granted at `period_start` via a specific job.

### 2. Monthly Grants as Credit Lots
Instead of a separate "allowance" balance, monthly grants are issued as `CreditLot` records with:
- `lot_type`: `SUBSCRIPTION_GRANT`
- `expires_at`: `period_end` (Use-it-or-lose-it policy)
- `priority`: High (consumed before Top-Up lots)

### 3. Overage Policies
Defined in `Plan.features` JSON:
- **`overage_policy`**:
  - `block`: Stop credit usage when grant is exhausted (Strict limits).
  - `paygo`: Allow usage of Top-Up lots after grant exhaustion (Default for paid tiers).

### 4. Spend Order
Defined in `Plan.features` JSON:
- **`spend_order`**: `allowance_first` (Default).
  - Allocator prefers `SUBSCRIPTION_GRANT` lots over `TOPUP` lots.

## Data Model Changes

### New Table: `SubscriptionPeriod`
```python
class SubscriptionPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    period_start: datetime
    period_end: datetime
    status: str = Field(default="OPEN") # OPEN, CLOSED
    granted_credits: int
    grant_lot_id: Optional[int] = Field(foreign_key="creditlot.id")
    created_at: datetime
    
    # Validation: Unique (subscription_id, period_start)
```

### Updates
- **`CreditLot`**: Ensure `lot_type` supports `SUBSCRIPTION_GRANT`.
- **`Plan.features`**: Add Schema for Phase 3 configuration.

## Logical Workflows

### A. Monthly Grant Job (Scheduler)
Frequency: Hourly (or Daily).
Logic:
1. Find active subscriptions where `now >= current_period_start`.
2. check if `SubscriptionPeriod` exists for this start time.
3. If not, create entries:
   - **Step 1**: Create `SubscriptionPeriod`.
   - **Step 2**: Create `CreditLot` (Type: SUBSCRIPTION_GRANT, Expire: Period End).
   - **Step 3**: Reset `Subscription.feature_usage` counters.
   - **Step 4**: Create `UsageLedger` entry (RESET/CREDIT).

### B. Expiry Job (Scheduler)
Frequency: Hourly.
Logic:
1. Find `OPEN` SubscriptionPeriods where `now > period_end`.
2. Mark `CreditLot` (Grant) as `EXPIRED`.
3. Set `credits_remaining = 0`.
4. Close `SubscriptionPeriod` status -> `CLOSED`.

### C. Consumption (Allocator Update)
Modify `CreditLotAllocator` to sort candidate lots:
1. Filter out expired lots.
2. Sort by:
   - Priority 1: `lot_type == SUBSCRIPTION_GRANT` (if `spend_order` == `allowance_first`).
   - Priority 2: `expires_at` ASC (FIFO).
   - Priority 3: `id` ASC.

## Configuration (Plan Features)

**Free Plan**:
```json
{
  "monthly_credits_included": 20,
  "overage_policy": "block",
  "spend_order": "allowance_first",
  "monthly_limits": { "ocr": 5, "voice": 0 }
}
```

**Standard Plan**:
```json
{
  "monthly_credits_included": 300,
  "overage_policy": "paygo",
  "spend_order": "allowance_first"
}
```

## Migration Plan
1. Create `SubscriptionPeriod` table.
2. Update `CreditLot` constraints if any.
3. Seed Phase 3 Plan configurations.
4. Deploy Jobs.
