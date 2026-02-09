# Database Schema Documentation: Billing System

This document outlines the database schema for the Uask billing, subscription, and credit management system.

## 1. Core User & Subscription
### `User` (partial)
Core user record containing billing state.
* `subscription_tier`: Legacy tier string.
* `stripe_customer_id`: Link to Stripe.
* `credits_balance`: Denormalized total usable credit balance.

### `Plan`
Product definitions for recurring subscriptions.
* `name`, `slug`, `is_active`
* `price_monthly_cents`, `price_yearly_cents`
* `credits_per_month`: Basic allowance grant.
* `overage_policy`: `BLOCK` or `PAYGO`.
* `features` (JSON): Entitlement flags (e.g., `allow_plot`, `allow_verify`).
* `multipliers` (JSON): Cost configuration per action/tier.

### `Subscription`
Tracks an active user plan.
* `user_id`, `plan_id`, `status` (`active`, `past_due`, `cancelled`)
* `current_period_start`, `current_period_end`
* `credits_balance`: Credits remaining in the current subscription grant.
* `credits_used_this_period`: Accumulator for usage tracking.
* `feature_usage` (JSON): Counters for OCR/Voice/Plot actions.
* `auto_renew`: Boolean flag.

### `SubscriptionPeriod`
Historical record of each billing cycle for a subscription.
* `subscription_id`, `period_start`, `period_end`
* `grant_amount`: Credits granted at start.
* `used_amount`: Credits consumed during this cycle.

---

## 2. Credits & Ledger
### `CreditLot`
Individually trackable "chunks" of credits (Top-ups, Grants, Promos).
* `user_id`, `lot_type` (`TOPUP`, `GRANT`, `PROMO`, `REFUND`)
* `credits_total`, `credits_remaining`
* `amount_paid`, `currency`, `external_ref`
* `expires_at`, `purchased_at`
* `status` (`ACTIVE`, `EXPIRED`, `DEPLETED`)

### `CreditLotConsumption`
Auditable link between a usage event and the specific lots consumed.
* `credit_lot_id`, `usage_ledger_id`, `amount`, `direction` (`DEBIT`, `REFUND`)

### `UsageLedger`
Low-level transaction log for subscription balance movements.
* `subscription_id`, `transaction_type` (`DEBIT`, `CREDIT`, `REFUND`, `RESET`)
* `amount`, `balance_after`
* `reference_id`: Links to Request/Payment.

### `CreditHold`
Temporary reservation of credits before a transaction finalizes.
* `request_id`, `reserved_credits`, `status` (`held`, `released`, `released_void`)

---

## 3. Payments & Top-Ups
### `Payment`
Stripe-linked payment records.
* `external_id`: Stripe PaymentIntent or Charge ID.
* `amount_cents`, `currency`, `status` (`succeeded`, `failed`, `pending`)
* `kind`: `TOPUP` or `SUBSCRIPTION`.

### `TopUpProduct`
Catalog of available credit bundles.
* `code`, `name`, `credits`, `price_usd`.

### `TopUpOrder`
Local state tracking for a checkout session.
* `stripe_checkout_session_id`, `status` (`pending`, `completed`, `expired`).

---

## 4. Invoicing
### `Invoice`
Immutable record of a financial transaction or usage statement.
* `invoice_number`: Unique sequential ID (e.g., `INV-2026-0001`).
* `kind`: `RECEIPT` (Top-up) or `USAGE_STATEMENT`.
* `total_amount`, `currency`, `status` (`PAID`, `VOIDED`, `OPEN`).
* `html_rendered`: Cached stylized version for emission.

### `InvoiceLineItem`
Details for individual charges on an invoice.
* `description`, `quantity`, `unit_price`, `amount`.

### `InvoiceSequence`
Counters for thread-safe invoice number generation.

---

## 5. Metrics & Logistics
### `BillingLedger`
The high-level high-visibility log for mathematical solve actions.
* `request_id`, `action_type`, `status` (`CHARGED`, `VOIDED`, `FAILED_NSF`).
* `provider_cost_usd`: Actual cost from LLM provider.
* `charge_usd`: Calculated user price.
* `credits_charged`: Final credit deduction.
* `credits_before`, `credits_after`: Snapshot balance.
* `markup_multiplier`, `fixed_fee_usd`.

### `ProviderModelPricing`
Live pricing configurations for LLM models.
* `provider`, `model`, `price_in`, `price_out`, `cache_read_price`.

### `LlmUsageLedger` (Follow-up Chat)
Specific tracking for follow-up chat session costs.
* `solve_session_id`, `message_role`, `tokens_in`, `tokens_out`, `cost_usd`.

### `StripeEvent`
Webhook deduplication and audit trail.
* `stripe_event_id`, `type`, `processed_at`, `process_status`.

---

## Entity-Relationship Summary
- **User (1) <-> Subscription (1)**
- **Subscription (1) <-> SubscriptionPeriod (N)**
- **User (1) <-> CreditLot (N)**
- **CreditLot (1) <-> CreditLotConsumption (N) <-> UsageLedger (1)**
- **User (1) <-> Invoice (N)**
- **Payment (1) <-> CreditLot (1)** (For TOPUP kinds)
- **RequestEvent (1) <-> BillingLedger (1)**
