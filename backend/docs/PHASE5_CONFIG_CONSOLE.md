# Phase 5: Payment Configuration Console

## Overview
The Payment Configuration Console (`/adminpayments/config`) provides a centralized, auditable interface for managing the economic parameters of the uask.ai billing system. This includes model pricing for `gpt-5-mini`, internal credit values, Stripe price mappings, and tax/invoice branding.

## Objectives
- **Centralized Control**: One dedicated URL for all payment-related setup.
- **Audit Integrity**: All changes require a "reason" and are logged with user ID, timestamps, and before/after diffs.
- **Economic Transparency**: Easily update token costs and credit values as provider prices fluctuate.

## Main Sections

### 1. Provider Pricing (`gpt-5-mini`)
- **Versioned Pricing**: Pricing entries are active within specific time ranges.
- **No Overlaps**: Creating a new pricing row starting at time $T$ automatically retires any existing active row at time $T$.
- **Immutability**: Active or past pricing rows cannot be edited. Instead, a new version must be deployed. Future-dated rows (if supported in the future) can be edited until they become active.
- **Soft Delete**: Pricing is never "hard deleted". Instead, entries are marked as `INACTIVE`.

### 2. Credit Economics
- **Credit Value**: Define the USD value of 1 credit Lot (e.g. $0.10).
- **Multipliers**: Set multipliers for different subscription tiers (e.g. RESEARCH = 2.0x).
- **Fixed Fees**: Configure flat credit costs for specific features like OCR or Voice.
- **Minimum Charge**: Enforce a minimum credit deduction per operation.

### 3. Stripe Setup
- **Environment Verification**: Real-time check if `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are configured.
- **Price Mappings**: Bind internal product codes (e.g. `topup-60`) to Stripe Price IDs. This allows the system to remain decoupled from Stripe's specific identifiers.

### 4. Tax & Invoice Branding
- **Tax Mode**: Select between `NONE`, `ESTIMATED`, and `FINAL`.
- **Branding**: Configure company name, address, and footer text displayed on generated invoices.

## Database Models & Tables

### `ProviderModelPricing`
- `provider`: (openai, etc)
- `model`: (gpt-5-mini)
- `price_in_per_1m`: Input token cost per 1M.
- `price_out_per_1m`: Output token cost per 1M.
- `price_cached_in_per_1m`: Cached input cost.
- `effective_from`, `effective_to`: Period of activity.
- `status`: ACTIVE/INACTIVE.

### `ProviderPricingAuditEvent`
- Tracks every `CREATE`, `UPDATE`, or `RETIRE` action on pricing.
- Stores `before_json` and `after_json` for forensics.

### `SystemConfigVersion`
- Stores global settings as JSON versions.
- Enables "Time Travel" to see past configurations and perform reverts.

## API Specification

- `GET /api/admin/payments/config`: Current settings + History.
- `PUT /api/admin/payments/config`: Update settings (Requires `reason`).
- `GET /api/admin/payments/pricing`: List entries.
- `POST /api/admin/payments/pricing`: Create new version.
- `DELETE /api/admin/payments/pricing/{id}`: Soft-delete/Retire.

## Demo & Verification
Run the sample invoice generator to verify the system can produce all Phase 5 document types:
```bash
python backend/scripts/demo_phase5_invoices_samples.py
```
This script will:
1. Generate a **Top-Up Receipt**.
2. Generate a **Subscription Invoice** (mirrored).
3. Generate a **Credit Note / Adjustment**.
4. Output the provider cost math to prove token billing precision.
