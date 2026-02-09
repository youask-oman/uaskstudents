# DEV Database Recreate & Seed Log

**Date:** 2026-02-09T22:26:13.139154+00:00  
**Status:** SUCCESS  
**Alembic Revision:** `25e7fcf4d1c5 (head)`

## 1. Execution Summary
Refreshed DEV database with full production seed dataset + DEV fixtures.

## 2. Row Counts
| Table | Count | Expected | Status |
|---|---|---|---|
| `school` | 117960 | 117960 | OK |
| `prompt_templates` | 10 | - | OK |
| `prompt_bindings` | 9 | - | OK |
| `json_schemas` | 8 | - | OK |
| `credit_program_definition` | 0 | 4 | OK |
| `plan` | 4 | 4 | OK |
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
[22:24:35] SECTION: Preflight Check
[22:24:35] SECTION: Nuke DB
[22:24:35] Truncating 70 tables...
[22:24:36] SECTION: Migrations
[22:24:36] CMD: alembic upgrade head
[22:24:38] SUCCESS after 1.24s
[22:24:38] STDOUT:

[22:24:38] CMD: alembic current
[22:24:39] SUCCESS after 1.23s
[22:24:39] STDOUT:
25e7fcf4d1c5 (head)

[22:24:39] SECTION: Seeding
[22:24:39] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[22:25:32] SUCCESS after 53.09s
[22:25:32] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=8 created=8 updated=0 skipped=0
  creditprogramdefinition: row_count=4 created=4 updated=0 skipped=0
  plan: row_count=4 created=4 updated=0 s...
[22:25:32] SECTION: Verification
[22:25:32] CMD: python -m scripts.verify_seed_schema_completeness
[22:25:33] SUCCESS after 1.22s
[22:25:33] STDOUT (snippet):
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
      "crop",
      "devicesignuplog",
      "adminnote",
      "ocrchoice",
      "ocrquestion",
      "systemconfig",
      "voicejob",
 ...
[22:25:33] SECTION: Smoke Tests
[22:25:33] CMD: pytest tests/seeding/ -q
[22:25:55] SUCCESS after 21.94s
[22:25:55] STDOUT:
....                                                                     [100%]
4 passed in 20.22s

[22:25:55] Running smoke tests...
[22:25:55] CMD: pytest tests/smoke/ -q
[22:26:11] SUCCESS after 16.23s
[22:26:11] STDOUT (snippet):
.....                                                                    [100%]
=============================== warnings summary ===============================
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_http_exception_passthrough.py::test_http_exception_404_passthrough
tests/smoke/test_http_exception_p...
[22:26:11] SECTION: Generating Report
... (see console for full logs)
```
