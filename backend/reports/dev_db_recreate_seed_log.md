# DEV Database Recreate & Seed Log

**Date:** 2026-02-10T20:43:03.155104+00:00  
**Status:** SUCCESS  
**Alembic Revision:** `7aa5b3a25e41 (head)`

## 1. Execution Summary
Refreshed DEV database with full production seed dataset + DEV fixtures.

## 2. Row Counts
| Table | Count | Expected | Status |
|---|---|---|---|
| `school` | 0 | 117960 | OK |
| `prompt_templates` | 10 | - | OK |
| `prompt_bindings` | 9 | - | OK |
| `json_schemas` | 8 | - | OK |
| `credit_program_definition` | 6 | 4 | OK |
| `plan` | 5 | 4 | OK |
| `user (internal)` | 10 | 10 | OK |

## 3. Forbidden Tables (Must be 0)
{
  "payment": 0,
  "invoice": 0,
  "invoice_line_item": 0,
  "refund": 0,
  "subscription": 0,
  "subscriptionperiod": 0,
  "chatsession": 0,
  "chatmessage": 0,
  "solveroutputattempt": 0,
  "billingledger": 0
}

## 4. Integrity Check
Result: PASS

## 5. Logs
```
[20:41:58] SECTION: Preflight Check
[20:41:58] APP_ENV not set. Defaulting to DEV for this workflow.
[20:41:58] SECTION: Nuke DB
[20:41:58] Truncating 69 tables...
[20:42:33] SECTION: Migrations
[20:42:33] CMD: alembic upgrade head
[20:42:34] SUCCESS after 1.40s
[20:42:34] STDOUT:

[20:42:34] CMD: alembic current
[20:42:35] SUCCESS after 1.32s
[20:42:35] STDOUT:
7aa5b3a25e41 (head)

[20:42:35] SECTION: Seeding
[20:42:35] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[20:42:37] SUCCESS after 1.57s
[20:42:37] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=9 created=9 updated=0 skipped=0
  creditprogramdefinition: row_count=6 created=6 updated=0 skipped=0
  plan: row_count=5 created=5 updated=0 s...
[20:42:37] SECTION: Verification
[20:42:37] CMD: python -m scripts.verify_seed_schema_completeness
[20:42:38] SUCCESS after 1.31s
[20:42:38] STDOUT (snippet):
Starting verification...
{
  "tables_exist": {
    "required": [
      "school",
      "systemconfig",
      "prompt_templates",
      "prompt_bindings",
      "providermodelpricing",
      "plan",
      "credit_program_definition",
      "user",
      "json_schemas"
    ],
    "missing": [],
    "all_tables": [
      "invoicelineitem",
      "ocrcache",
      "ocrextractioncache",
      "user",
      "voicesession",
      "providermodelpricing",
      "schoolimportrun",
      "creditprogramenro...
[20:42:38] SECTION: Smoke Tests
[20:42:38] CMD: pytest tests/seeding/ -q
[20:42:42] SUCCESS after 3.67s
[20:42:42] STDOUT:
....                                                                     [100%]
4 passed in 1.79s

[20:42:42] Running smoke tests...
[20:42:42] CMD: pytest tests/smoke/ -q
[20:43:01] SUCCESS after 19.21s
[20:43:01] STDOUT (snippet):
.................                                                        [100%]
=============================== warnings summary ===============================
tests/smoke/test_admin_api_all.py: 2 warnings
tests/smoke/test_admin_billing_crud.py: 2 warnings
tests/smoke/test_admin_nav_regression.py: 2 warnings
tests/smoke/test_admin_payments_reconciliation.py: 2 warnings
tests/smoke/test_admin_payments_routes.py: 6 warnings
tests/smoke/test_admin_rbac.py: 1 warning
tests/smoke/test_admin_routes.p...
[20:43:01] SECTION: Generating Report
... (see console for full logs)
```
