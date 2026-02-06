# Phase 0 Billing Audit & Gap Report

## 1. Current State Assessment

### 1.1 Data Structures
We have two distinct billing/cost domains that are currently loosely coupled:

**A. User Billing (Credits)**
- **Source of Truth:** `Subscription`, `UsageLedger`, `BillingLedger`.
- **Pricing Logic:** `app/services/pricing_service.py`.
- **Config Storage:** `SystemConfig` (key="pricing") and `SystemConfigVersion`.
- **Execution:** `app/services/billing_service.py` manages the ledger (Pending -> Settled).
- **Status:** Robust for credits, handles estimates and reconciliation.

**B. Provider Cost (Operations)**
- **Source of Truth:** `RequestEvent` (primary telemetry), `SolverOutputAttempt`.
- **Pricing Logic:** `app/services/admin/analytics_service.py` -> `_calc_cost`.
- **Config Storage:** Hardcoded `MODEL_PRICING_PER_MILLION` dictionary in code, with optional ENV override.
- **Execution:** Calculated on-read in the analytics dashboard.
- **Status:** **Fragile**. Relies on hardcoded values, not versioned, not auditable in DB.

### 1.2 Telemetry & Visibility
- **RequestEvent:** Captures `tokens_in`, `tokens_out`, `model`, `provider`, `cost_usd`.
  - *Risk:* `cost_usd` is written at event creation time (?), or calculated on fly? `record_request_event` writes it if present in payload.
  - *Gap:* The current "Provider Cost" is often just an estimate calculated *after the fact* using the hardcoded dictionary in `analytics_service.py`.

- **SolverOutputAttempt:** Captures `provider`, `model`, `latency_ms`, `attempt_number`.
  - Linked to `RequestEvent` via `request_id`.

## 2. Identified Gaps (Phase 0 Missing Items)

### 2.1 "True Cost" Visibility
- **Hardcoded Prices:** Provider costs are hardcoded in `analytics_service.py`. If OpenAI changes prices, or we switch to Anthropic, historical cost calculations might change if not persisted, or we have to update code.
- **Missing Model Pricing Table:** There is no database table defining "Provider X Model Y costs $Z per 1M tokens" valid from Date A to Date B.
- **Auditability:** We cannot verify *why* a specific cost was assigned to a request from last month.

### 2.2 Database Keys & Indexes
- **Indexes:** `RequestEvent` has indexes on `request_id`, `user_id`, `created_at`.
- **Constraints:** No foreign key from `RequestEvent` to `ModelPrice` (which doesn't exist).
- **Consistency:** `BillingLedger` stores `actual_usage_json` and `pricing_snapshot_json` (User Side), which is good. `RequestEvent` does not store a snapshot of the provider rate used.

### 2.3 Admin Capability
- **Missing Dashboard:** No interface to view "Provider Costs vs User Revenue" side-by-side.
- **Missing Config UI:** Pricing changes currently require code deploys or raw JSON edits in existing Admin.

## 3. Implementation Plan (Phase 0)

### 3.1 New Database Schema
We will introduce `ProviderModelPricing` (or similar) to strictly define provider costs.

```python
class ProviderModelPricing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True) # openai, anthropic
    model: str = Field(index=True)    # gpt-4o, claude-3-5-sonnet
    
    price_in_per_1m: float
    price_out_per_1m: float
    price_cached_in_per_1m: Optional[float] = 0.0
    
    currency: str = Field(default="USD")
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    effective_to: Optional[datetime] = None # Null = current
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[int] = Field(default=None)
```

### 3.2 Service Layer
1.  **`ProviderPricingService`**: Reading the `ProviderModelPricing` table to find the active price for a given (provider, model, timestamp).
2.  **`CostEstimationService`**: Replaces the logic in `analytics_service.py`.
    -   Input: `events: List[RequestEvent]`
    -   Output: Augmented events with `provider_cost` calculated using the *historically accurate* pricing from `ProviderModelPricing`.

### 3.3 Dashboard (`/adminpayments`)
- **Overview:** Total Provider Cost, Total User Spend (Credits value), Margin Estimate.
- **Pricing Config:** UI to add new pricing rows (e.g. "Effective Now: GPT-4o input $2.50").
- **Cost Explorer:** Filterable list of requests with their calculated provider costs.

### 3.4 Migration Strategy
- **Additive Only:** We will create the new table.
- **Seed Data:** We will seed it with the current values from `MODEL_PRICING_PER_MILLION`.
- **Zero Downtime:** Existing flows continue to use hardcoded logic until we flip the switch (or we just use the new service for the new Dashboard first).

## 4. Risks & Mitigations
- **Perf:** querying pricing for every request in a list might be N+1.
  - *Mitigation:* Cache active pricing in memory/Redis. Bulk fetch pricing history.
- **Data mismatch:** `model` names must match exactly (e.g. `gpt-4o` vs `gpt-4o-2024-05-13`).
  - *Mitigation:* Normalize model names in `ProviderModelPricing`.

## 5. Next Steps
1. Create `ProviderModelPricing` migration.
2. Seed with current hardcoded defaults.
3. Build `ProviderPricingService`.
4. Build `/adminpayments` UI.
