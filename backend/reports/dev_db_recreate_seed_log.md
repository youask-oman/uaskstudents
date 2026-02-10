# DEV Database Recreate & Seed Log

**Date:** 2026-02-10T05:44:59.782952+00:00  
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
[05:43:52] SECTION: Preflight Check
[05:43:52] APP_ENV not set. Defaulting to DEV for this workflow.
[05:43:52] SECTION: Nuke DB
[05:43:52] Truncating 70 tables...
[05:44:30] SECTION: Migrations
[05:44:30] CMD: alembic upgrade head
[05:44:31] SUCCESS after 1.48s
[05:44:31] STDOUT:

[05:44:31] CMD: alembic current
[05:44:33] SUCCESS after 1.47s
[05:44:33] STDOUT:
7aa5b3a25e41 (head)

[05:44:33] SECTION: Seeding
[05:44:33] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[05:44:34] SUCCESS after 1.55s
[05:44:34] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=9 created=9 updated=1 skipped=0
  creditprogramdefinition: row_count=6 created=6 updated=0 skipped=0
  plan: row_count=5 created=5 updated=0 s...
[05:44:34] SECTION: Verification
[05:44:34] CMD: python -m scripts.verify_seed_schema_completeness
[05:44:35] SUCCESS after 1.32s
[05:44:35] STDOUT (snippet):
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
      "canonicalproblem",
      "chatsession",
      "usersavedsolution",
      "ocrextractioncache",
      "voicesession",
      "question_identity_cache",
      "creditprogramgrantlog"...
[05:44:35] SECTION: Smoke Tests
[05:44:35] CMD: pytest tests/seeding/ -q
[05:44:39] SUCCESS after 3.83s
[05:44:39] STDOUT:
....                                                                     [100%]
4 passed in 1.99s

[05:44:39] Running smoke tests...
[05:44:39] CMD: pytest tests/smoke/ -q
[05:44:58] SUCCESS after 18.49s
[05:44:58] STDOUT (snippet):
.............                                                            [100%]
=============================== warnings summary ===============================
tests/smoke/test_admin_api_all.py: 2 warnings
tests/smoke/test_admin_billing_crud.py: 2 warnings
tests/smoke/test_admin_nav_regression.py: 2 warnings
tests/smoke/test_admin_rbac.py: 1 warning
tests/smoke/test_admin_routes.py: 9 warnings
tests/smoke/test_http_exception_passthrough.py: 3 warnings
tests/smoke/test_legacy_plan_mutations.py: ...
[05:44:58] SECTION: Generating Report
... (see console for full logs)
```
