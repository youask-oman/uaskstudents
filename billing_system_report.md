# Technical Audit & Documentation: Uask Billing System

## 1. Executive Summary
The Uask Billing System is a hybrid credit-subscription model designed to manage high-cost LLM interactions (OCR, Solving, Plotting) with precision. It implements a **ledger-first architecture** with two-phase commit logic for mathematical solve actions, ensuring that user balances are only deducted for successful, validated outputs.

**Key Structural Pillars:**
1.  **Subscription Layer:** Entitlement management with monthly credit grants and overage controls (`BLOCK` vs. `PAYGO`).
2.  **Credit Layer:** FIFO (First-In-First-Out) consumption of mixed credit lots (Grants, Top-ups, Promos).
3.  **Two-Phase Ledgering:** Separation of cost estimation (Hold) from final reconciliation (Settle/Charge).
4.  **Usage Metering:** Granular token-level cost tracking tied to live provider pricing.

---

## 2. The Credit Lifecycle
### Earn (Creation)
Credits enter the system via three primary channels:
-   **Subscription Grants:** Automatically issued at the start of a `SubscriptionPeriod`.
-   **Direct Top-Ups:** Purchased bundles fulfilled via Stripe or Admin manual confirmation.
-   **Promotional Grants:** Issued by system events or admin actions.
All credits are stored as `CreditLot` entries with an expiry date.

### Spend (Consumption)
The `CreditLotAllocator` implements a strict **FIFO** strategy:
1.  Prioritizes **Subscription Grants** (non-refundable usually).
2.  Then consumes **Purchased Top-Ups** ordered by expiry date (earliest first).
3.  Then consumes **Promotional credits**.

### Hold & Settle (Two-Phase Billing)
For complex AI actions (Math Solving):
1.  **Initiate Hold:** Before calling the LLM, the system checks the user's usable balance and creates a `CreditHold` reservation.
2.  **Finalize Charge:** After execution, the system reads actual token usage from the `RequestEvent`, calculates the commercial price based on the current `ProviderModelPricing` and `multiplier`, and executes the final `Deduct` from the wallet.

---

## 3. Subscription Mechanics
Subscriptions are driven by the `Plan` model, which defines:
-   **Quota:** `credits_per_month`.
-   **Overage Policy:**
    -   `BLOCK`: Action fails if credits run out.
    -   `PAYGO`: Action succeeds by drawing from the user's purchased `TOPUP` lots.
-   **Entitlements:** Boolean flags for features like Image/PDF solving, Plotting, and Verification.
-   **Multipliers:** Tier-based multipliers (FREE=1x, STANDARD=2x, RESEARCH=4x) applied to the base provider cost to calculate the user credit price.

---

## 4. Usage Metering & Token Accounting
Uask does not charge a flat fee per question; it charges based on **Commercial Real-Time Value**:
1.  **Token Capture:** Every LLM response returns usage statistics (input/output tokens).
2.  **Cost Estimation:** The `cost_estimation_service` looks up the `price_in` and `price_out` for the specific model used.
3.  **Credit Mapping:**
    -   `ProviderCostUSD = (TokensIn * PriceIn) + (TokensOut * PriceOut)`
    -   `UserChargeUSD = (ProviderCostUSD * Multiplier) + FixedFee`
    -   `ChargedCredits = UserChargeUSD / CreditValueUSD (default $0.02)`
4.  **Rounding:** Credits are typically rounded `CEIL` to the nearest integer.

---

## 5. Invoicing & Auditability
The `Invoice` system generates immutable records for every financial event:
-   **Top-Up Receipts:** Issued immediately upon successful payment.
-   **Usage Statements:** Can be generated periodically to summarize charges.
-   **Immutability:** Once an invoice is generated and assigned an `invoice_number` via `InvoiceSequence`, it cannot be deleted; only voided.

---

## 6. Flow Walkthrough (Code References)

### Flow A: Purchasing Credits
1.  Frontend calls `POST /api/v1/topups/stripe/checkout`.
2.  `top_up_service` creates a Stripe Checkout Session.
3.  Stripe Webhook (`checkout.session.completed`) is caught by `stripe_webhook_processor`.
4.  `credit_wallet_service.add_credits` creates a new `CreditLot(TOPUP)`.
5.  `invoice_service` generates an `Invoice(RECEIPT)`.

### Flow B: Solving a Problem
1.  API calls `billing_service.initiate_hold(request_id, estimated_credits)`.
2.  LLM executes; `RequestEvent` logs tokens.
3.  `solver_v3` calls `billing_service.finalize_transaction(...)`.
4.  Wait logic computes actual cost.
5.  `credit_wallet_service.deduct_credits` is called.
6.  `credit_lot_allocator` updates `CreditLot.credits_remaining` across one or more lots.

---

## 7. Gaps, Risks, and Bugs (Brutally Honest Audit)

### Critical Risks
-   **Circular Dependencies:** `credit_wallet_service` and `credit_lot_allocator` have complex cross-imports that could lead to runtime instantiation failures if refactored improperly.
-   **Float Precision:** Credit balances use `Float` (`double precision`). Over years of millions of transactions, tiny precision errors (0.0000001) will accumulate. **Recommendation:** Switch to `Decimal` for all financial math.
-   **Race Conditions:** High-frequency deduplication of credits depends on `sub.credits_balance -= amount`. Without explicit row-level locking (`SELECT ... FOR UPDATE`), concurrent solving requests from the same user could cause "double spending" or "over-spend" beyond the block limit.

### Logic Gaps
-   **Daily Cap Checking:** The `estimate_credits` endpoint has a "TODO" for accurate daily cap tracking. Currently, it assumes `daily_ok = True`.
-   **Refund Complexity:** Refunding a transaction that spanned multiple `CreditLots` is difficult. The system tries to restore FIFO order, but "Expired" lots make this complex.
-   **Stripe Replay Protection:** While `StripeEvent` deduplicates by ID, the logic for handling "Payment Success" after a "Payment Failed" event for the same Intent is not fully robust in the webhook processor.

---

## 8. Migration Readiness: Move to Credit-Only Plan
To transition to a 100% credit-based system (removing legacy subscription "balance"), the following must be done:

### Phase 1: Data Migration
1.  Convert all existing `Subscription.credits_balance` into `CreditLot(GRANT)` entries.
2.  Zero out the legacy `credits_balance` columns in the `Subscription` table.
3.  Unify `UsageLedger` and `BillingLedger` into a single `FinancialLedger`.

### Phase 2: Logic Refactoring
-   Modify `billing_service` to ignore subscription periods and always query the unified `credit_wallet_service`.
-   Change "Plans" to strictly define **Credit Top-Up Multipliers** or **Monthly Gifts** rather than internal "balances".

---

## 9. Next Steps / Recommendations
1.  **Decimal Migration:** Immediately migrate credit and USD columns to `Numeric(20, 10)` in Postgres.
2.  **Strict Locking:** Implement `with session.begin_nested()` and row-level locks in `deduct_credits`.
3.  **Unified Ledger:** Merge `BillingLedger` and `UsageLedger` to simplify admin auditing.
4.  **Auto-Reconciliation:** Implement the Nightly Reconciler (`StripeReconciler`) full logic to check Stripe totals vs. `CreditLot` totals daily.
