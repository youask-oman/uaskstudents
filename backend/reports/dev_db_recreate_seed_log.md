# DEV Database Recreate & Seed Log

**Date:** 2026-02-10T02:30:21.668405+00:00  
**Status:** SUCCESS  
**Alembic Revision:** `7aa5b3a25e41 (head)`

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
[02:28:14] SECTION: Preflight Check
[02:28:14] APP_ENV not set. Defaulting to DEV for this workflow.
[02:28:14] SECTION: Nuke DB
[02:28:14] Truncating 70 tables...
[02:28:15] SECTION: Migrations
[02:28:15] CMD: alembic upgrade head
[02:28:16] SUCCESS after 1.23s
[02:28:16] STDOUT:

[02:28:16] CMD: alembic current
[02:28:17] SUCCESS after 1.55s
[02:28:17] STDOUT:
7aa5b3a25e41 (head)

[02:28:17] SECTION: Seeding
[02:28:17] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[02:29:11] SUCCESS after 54.06s
[02:29:11] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=8 created=8 updated=0 skipped=0
  creditprogramdefinition: row_count=4 created=4 updated=0 skipped=0
  plan: row_count=5 created=5 updated=0 s...
[02:29:11] SECTION: Verification
[02:29:11] CMD: python -m scripts.verify_seed_schema_completeness
[02:29:13] SUCCESS after 1.21s
[02:29:13] STDOUT (snippet):
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
      "usagelog",
      "upload",
      "canonicalsolution",
      "json_schemas"...
[02:29:13] SECTION: Smoke Tests
[02:29:13] CMD: pytest tests/seeding/ -q
[02:29:35] SUCCESS after 22.12s
[02:29:35] STDOUT:
....                                                                     [100%]
4 passed in 20.31s

[02:29:35] Running smoke tests...
[02:29:35] CMD: pytest tests/smoke/ -q
[02:30:20] SUCCESS after 45.12s
[02:30:20] STDOUT (snippet):
............                                                             [100%]
=============================== warnings summary ===============================
tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
tests/smoke/test_admin_rbac.py::test_admin_rbac_enforcement
  /app/app/auth.py:38: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(date...
[02:30:20] SECTION: Generating Report
... (see console for full logs)
```
