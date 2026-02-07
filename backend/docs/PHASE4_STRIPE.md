# Phase 4: Stripe Payments Integration

## Overview
Phase 4 implements a robust, idempotent Stripe integration for Top-Up credit bundles and Subscription plans. It focuses on absolute data integrity, resilience against webhook delivery issues, and clear reconciliation.

## Key Components

### 1. Data Integrity & Idempotency
- **Event Storage**: Every incoming Stripe webhook is recorded in the `StripeEvent` table before processing. The `stripe_event_id` is unique, preventing duplicate processing of the same event.
- **Fulfillment**: Crediting user accounts (Top-Ups) or activating subscriptions only happens after Stripe confirms payment via webhooks. We do not trust client-side callbacks.
- **Payment Lifecycle**: The `Payment` table tracks the external status directly from Stripe (e.g., `SUCCEEDED`, `FAILED`, `REFUNDED`).

### 2. Top-Up Flow (One-time)
1. **Initiation**: User selects a bundle. Backend creates a `TopUpOrder` with status `CREATED`.
2. **Checkout**: Backend creates a Stripe Checkout Session. `TopUpOrder` status updates to `CHECKOUT_CREATED`. Metadata includes `topup_order_id` and `user_id`.
3. **Webhook (`checkout.session.completed`)**: 
    - Verify signature.
    - Record `StripeEvent`.
    - Upsert `Payment` record.
    - Create `UsageLedger` and `CreditLot` (fulfillment).
    - Mark `TopUpOrder` as `FULFILLED`.

### 3. Subscription Flow (Recurring)
1. **Initiation**: User selects a plan. Backend creates a Stripe Checkout Session for a subscription.
2. **Webhook (`customer.subscription.created/updated`)**:
    - Update/Create `SubscriptionBillingLink`.
    - Align local `Subscription` status and period dates.
3. **Credits**: Handled by existing Phase 3 jobs, which now synchronize with Stripe period dates retrieved from webhooks.

### 4. Reconciliation Job
A nightly process that scans recent Stripe events and local records to identify:
- Paid Stripe intents missing a local `Payment`.
- Fulfilled `TopUpOrder` missing a `CreditLot`.
- Mismatched subscription states.
Identified issues are logged for admin review.

## State Machine: TopUpOrder
- `CREATED`: Initial intent.
- `CHECKOUT_CREATED`: Stripe session generated.
- `PAID`: Payment confirmed but not yet fulfilled (transitional).
- `FULFILLED`: Credits granted, process complete.
- `FAILED` / `CANCELED`: Terminal negative states.

## Database Additions
- `StripeEvent`: Ledger of all received webhooks.
- `TopUpOrder`: Tracks credit purchase intent to fulfillment.
- `SubscriptionBillingLink`: Maps internal subscriptions to Stripe objects.
- `Payment` (Extended): Tracking Stripe payment intents and statuses.
