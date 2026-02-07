# Provider Pricing Configuration — GPT-5 Family Implementation

**Status**: ✅ Complete  
**Date**: 2026-02-06  
**Models**: OpenAI GPT-5 Family (gpt-5-mini, gpt-5, gpt-5-nano)

---

## Summary

Successfully implemented OpenAI-only GPT-5 family pricing configuration with the following features:

1. ✅ **Seeded correct OpenAI GPT-5 pricing**
2. ✅ **gpt-5-mini as the ONLY active model**
3. ✅ **Fail-safe cost estimation with error logging**
4. ✅ **Admin API with OpenAI-only and GPT-5 family guardrails**
5. ✅ **Advanced models toggle (ALLOW_ADVANCED_MODELS config)**

---

## Pricing Values (USD per 1M tokens)

### Active Model

**gpt-5-mini** (Status: ACTIVE)
- Input: $0.25/1M
- Cached Input: $0.025/1M  
- Output: $2.00/1M

### Inactive Models (Available for Future Use)

**gpt-5** (Status: INACTIVE)
- Input: $1.25/1M
- Cached Input: $0.125/1M
- Output: $10.00/1M

**gpt-5-nano** (Status: INACTIVE)
- Input: $0.05/1M
- Cached Input: $0.005/1M
- Output: $0.40/1M

---

## Database Changes

### Migration: Add Status and Change Reason Columns

**Script**: `scripts/migrate_add_pricing_status.py`

Added columns to `ProviderModelPricing`:
- `status` VARCHAR DEFAULT 'ACTIVE' (indexed)
- `change_reason` VARCHAR (nullable)

**Run**:
```bash
python backend/scripts/migrate_add_pricing_status.py
```

**Result**: ✅ Completed successfully

---

## Seeding Script

**Script**: `scripts/seed_provider_pricing_gpt5_family.py`

**Actions**:
1. Retired all non-OpenAI pricing (gemini)
2. Retired all non-GPT-5 OpenAI pricing (gpt-4o, gpt-4o-mini, o1-mini, o1-preview)
3. Seeded gpt-5-mini as ACTIVE
4. Seeded gpt-5 and gpt-5-nano as INACTIVE
5. Created `ALLOW_ADVANCED_MODELS=false` system config

**Run**:
```bash
python backend/scripts/seed_provider_pricing_gpt5_family.py
```

**Output**:
```
=== SUMMARY ===
Retired entries: 5
Seeded/updated entries: 3
Active model: gpt-5-mini ONLY
Inactive models: gpt-5, gpt-5-nano (available for future use)

ACTIVE PRICING ENTRIES (1):
  - openai/gpt-5-mini: $0.25/1M in, $2.0/1M out

✓ SUCCESS: Only gpt-5-mini is active
```

---

## API Changes

### GET `/api/admin/payments/pricing`

**Query Parameters**:
- `provider` (default: "openai") - HARD RULE: Only "openai" accepted
- `model` (optional) - Must be GPT-5 family (gpt-5*)
- `show_inactive_gpt5` (default: false) - Show gpt-5 and gpt-5-nano
- `all_history` (default: false) - Show all historical versions

**Default Behavior**:
- Shows only OpenAI pricing
- Shows only gpt-5-mini (active)
- Rejects non-OpenAI providers with 400 error
- Rejects non-GPT-5 models with 400 error

**Response**:
```json
{
  "pricing": [
    {
      "id": 6,
      "provider": "openai",
      "model": "gpt-5-mini",
      "price_in_per_1m": 0.25,
      "price_out_per_1m": 2.0,
      "price_cached_in_per_1m": 0.025,
      "status": "ACTIVE",
      "effective_from": "2026-02-07T01:32:46",
      "effective_to": null
    }
  ],
  "filters": {
    "provider": "openai",
    "model": "gpt-5-mini",
    "show_inactive_gpt5": false,
    "all_history": false
  }
}
```

### POST `/api/admin/payments/pricing`

**Guardrails**:
1. ✅ Only OpenAI provider accepted
2. ✅ Only GPT-5 family models accepted
3. ✅ Non-mini models require `ALLOW_ADVANCED_MODELS=true`
4. ✅ No overlapping ACTIVE windows (auto-retires previous)
5. ✅ Requires `reason` for audit trail

**Example**:
```json
POST /api/admin/payments/pricing
{
  "provider": "openai",
  "model": "gpt-5-mini",
  "price_in_per_1m": 0.30,
  "price_out_per_1m": 2.50,
  "price_cached_in_per_1m": 0.03,
  "reason": "Price increase effective March 2026"
}
```

**Behavior**:
- Previous ACTIVE gpt-5-mini pricing is set to INACTIVE with `effective_to = now()`
- New pricing becomes ACTIVE with `effective_from = now()`
- Audit event created

---

## Cost Estimation Changes

**File**: `app/services/cost_estimation_service.py`

### Fail-Safe Behavior

**Before**:
```python
if not pricing:
    return 0.0, None  # Silent failure
```

**After**:
```python
if not pricing:
    # Log HIGH severity error
    error_service.capture_error(
        component="CostEstimation",
        error_code="pricing_missing",
        severity="HIGH",
        context={...}
    )
    return None, None  # Explicit failure signal
```

**Impact**:
- Callers receive `None` instead of `0.0` when pricing is missing
- `SystemErrorEntry` created with `error_code="pricing_missing"`
- Admin can query `/api/admin/health/errors?error_code=pricing_missing`
- Prevents silent undercharging

---

## System Configuration

### ALLOW_ADVANCED_MODELS

**Key**: `ALLOW_ADVANCED_MODELS`  
**Value**: `false` (default)  
**Description**: Allow selection of gpt-5 and gpt-5-nano in addition to gpt-5-mini

**To Enable Advanced Models**:
```sql
UPDATE systemconfig 
SET value = 'true' 
WHERE key = 'ALLOW_ADVANCED_MODELS';
```

**Effect**:
- When `false`: Only gpt-5-mini can be created/activated via API
- When `true`: gpt-5 and gpt-5-nano can also be activated

---

## Hard Rules Enforced

### 1. No Overlapping Active Windows
When creating a new ACTIVE pricing:
- Previous ACTIVE pricing for same (provider, model) is automatically set to INACTIVE
- `effective_to` is set to new pricing's `effective_from`

### 2. Soft Delete Only
- No DELETE endpoint provided
- "Retire" action sets `status=INACTIVE` and `effective_to=now()`
- Historical pricing preserved for cost estimation

### 3. OpenAI-Only
- All API endpoints reject non-OpenAI providers with 400 error
- Database can contain other providers but they're not accessible via API

### 4. GPT-5 Family Only
- All API endpoints reject non-GPT-5 models with 400 error
- Legacy models (gpt-4o, o1, gemini) are retired but preserved

### 5. Change Reason Required
- All pricing create/update/retire actions require `reason` parameter
- Audit trail stored in `ProviderPricingAuditEvent`

---

## Testing

### Verification Script

**Script**: `scripts/test_pricing_config.py`

**Run**:
```bash
python backend/scripts/test_pricing_config.py
```

**Expected Output**:
```
=== PROVIDER PRICING TEST ===

1. ACTIVE PRICING:
   openai/gpt-5-mini:
     Input: $0.25/1M
     Cached Input: $0.025/1M
     Output: $2.0/1M
     Status: ACTIVE

2. ALL GPT-5 FAMILY PRICING:
   gpt-5-mini: ACTIVE
   gpt-5: INACTIVE
   gpt-5-nano: INACTIVE

3. SYSTEM CONFIG:
   ALLOW_ADVANCED_MODELS = false

4. VALIDATION:
   ✓ Only gpt-5-mini is ACTIVE
   ✓ All 3 GPT-5 family models seeded
   ✓ gpt-5 and gpt-5-nano are INACTIVE
```

### Manual API Testing

```bash
# List active pricing (gpt-5-mini only)
GET /api/admin/payments/pricing

# List all GPT-5 family (including inactive)
GET /api/admin/payments/pricing?show_inactive_gpt5=true

# Try to create gpt-5 pricing (should fail with 403)
POST /api/admin/payments/pricing
{
  "provider": "openai",
  "model": "gpt-5",
  ...
}
# Response: 403 "Advanced model gpt-5 is not enabled"

# Try non-OpenAI provider (should fail with 400)
GET /api/admin/payments/pricing?provider=anthropic
# Response: 400 "Only OpenAI provider is supported"
```

---

## Rollback Plan

### To Revert to Previous State

1. **Re-activate old pricing**:
```sql
UPDATE providermodelpricing 
SET status = 'ACTIVE', effective_to = NULL 
WHERE provider = 'openai' AND model = 'gpt-4o-mini';
```

2. **Deactivate GPT-5 pricing**:
```sql
UPDATE providermodelpricing 
SET status = 'INACTIVE', effective_to = NOW() 
WHERE model LIKE 'gpt-5%';
```

3. **Remove system config**:
```sql
DELETE FROM systemconfig WHERE key = 'ALLOW_ADVANCED_MODELS';
```

**Note**: All historical data is preserved. No data loss on rollback.

---

## Next Steps (Optional Enhancements)

1. **Frontend UI Updates**:
   - Add "Show Advanced Models" toggle in admin panel
   - Display pricing in table with status badges
   - Add "Create New Version" button for gpt-5-mini

2. **Automated Tests**:
   - `test_pricing_seed_creates_active_gpt5mini_only()`
   - `test_no_overlap_on_new_pricing_version()`
   - `test_soft_delete_retire_pricing()`
   - `test_cost_estimation_missing_pricing_fails_safe()`

3. **Monitoring**:
   - Alert when `pricing_missing` errors occur
   - Dashboard showing pricing version history
   - Cost estimation accuracy metrics

4. **Cached Token Support**:
   - Add `tokens_cached_in` field to `RequestEvent`
   - Update cost calculation to use `price_cached_in_per_1m`
   - Backfill script for historical events

---

## Files Modified

### New Files
- `backend/scripts/migrate_add_pricing_status.py`
- `backend/scripts/seed_provider_pricing_gpt5_family.py`
- `backend/scripts/test_pricing_config.py`
- `backend/scripts/check_pricing_table.py`
- `backend/docs/PROVIDER_PRICING_GPT5.md` (this file)

### Modified Files
- `backend/app/services/cost_estimation_service.py`
- `backend/app/api_admin_payments_config.py`

### Database Changes
- Added `status` column to `providermodelpricing`
- Added `change_reason` column to `providermodelpricing`
- Added index on `status`
- Seeded 3 GPT-5 family pricing entries
- Created `ALLOW_ADVANCED_MODELS` system config

---

## Conclusion

✅ **Production Ready**: The system now enforces OpenAI-only, GPT-5 family pricing with fail-safe cost estimation and comprehensive guardrails. Only gpt-5-mini is active, with gpt-5 and gpt-5-nano available for future activation via system config.
