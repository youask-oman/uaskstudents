# Phase 5: Invoicing System

## Overview
Phase 5 implements a robust, immutable invoicing system to provide users with receipts and accounting records for their purchases (Top-ups) and subscription fees.

## Objectives
- Generate and persist invoices for Top-ups and Subscription billing.
- Mirror Stripe invoices for subscriptions to ensure consistency.
- Support adjustments (Credit Notes) for refunds and corrections.
- Provide a "Billing" UI for customers to view and download invoices.
- Provide an admin interface for invoice oversight and forensic drilldown.

## Data Model

### `Invoice`
The primary record of an accounting event (billing).
- `id`: PK
- `user_id`: Link to User
- `subscription_id`: (Optional) Link to Subscription
- `topup_order_id`: (Optional) Link to TopUpOrder
- `stripe_invoice_id`: (Optional) Stripe Invoice ID (for subscriptions)
- `stripe_payment_intent_id`: (Optional) Stripe PI ID
- `invoice_number`: Unique human-readable ID (e.g., `INV-2026-000001`)
- `kind`: `TOPUP`, `SUBSCRIPTION`, `ADJUSTMENT`
- `status`: `DRAFT`, `OPEN`, `PAID`, `VOID`, `UNCOLLECTIBLE`, `REFUNDED`, `PARTIALLY_REFUNDED`
- `currency`: Default `USD`
- `period_start`, `period_end`: Billing period (primarily for subscriptions)
- `subtotal_amount`, `tax_amount`, `total_amount`: Numeric totals
- `amount_paid`, `amount_due`: Settlement tracking
- `tax_mode`: `NONE`, `ESTIMATED`, `FINAL`
- `billing_address_json`: Snapshot of address at time of issue
- `issued_at`, `due_at`, `paid_at`: Timestamps
- `created_at`, `updated_at`: Metadata

### `InvoiceLineItem`
Individual components of an invoice.
- `id`: PK
- `invoice_id`: FK to Invoice
- `kind`: `TOPUP_CREDITS`, `SUBSCRIPTION_FEE`, `USAGE_CHARGE`, `REFUND`, `DISCOUNT`, `TAX`, `ADJUSTMENT`
- `description`: Human-readable text
- `quantity`: Numeric
- `unit_price`: Numeric
- `amount`: Numeric (Calculated)
- `payment_id`: (Optional) FK to Payment record
- `billing_ledger_id`: (Optional) FK to BillingLedger (for future usage-based billing)
- `metadata_json`: Audit trail

### `InvoiceSequence`
Atomic counter for generating monotonic invoice numbers.

## Business Rules

### 1. Top-up Invoices
Generated automatically when a `TopUpOrder` is marked as `PAID` and credits are fulfilled.
- Kind: `TOPUP`
- Status: `PAID`
- Line Item: `TOPUP_CREDITS`
- Reference: Linked to `TopUpOrder` and `Payment`.

### 2. Subscription Invoices
Mirrored from Stripe via webhooks (`invoice.paid`, `invoice.finalized`).
- Kind: `SUBSCRIPTION`
- Status: Transitions based on Stripe events.
- Synchronization: Fields are populated directly from the Stripe Invoice object.

### 3. Refunds & Adjustments
Represented as a new `Invoice` with `kind=ADJUSTMENT`.
- Marked with negative amounts.
- Status: `REFUNDED`.
- Linked via `metadata_json` or a specialized field (if needed) to the original invoice.

### 4. Immutability
Invoices are never edited. To change an issued invoice, it must be VOIDED and a new one issued, or an ADJUSTMENT invoice must be created.

## Webhook Mapping
- `invoice.finalized`: Create/Update `Invoice` in `OPEN` state.
- `invoice.paid`: Mark `Invoice` as `PAID`.
- `charge.refunded` / `invoice.refunded`: Create `ADJUSTMENT` invoice and update original status.
