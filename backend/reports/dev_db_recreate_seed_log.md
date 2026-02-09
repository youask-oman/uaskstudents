# DEV Database Recreate & Seed Log

**Date:** 2026-02-09T22:49:23.167277+00:00  
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
[22:47:23] SECTION: Preflight Check
[22:47:23] SECTION: Nuke DB
[22:47:23] Truncating 70 tables...
[22:47:25] SECTION: Migrations
[22:47:25] CMD: alembic upgrade head
[22:47:26] SUCCESS after 1.25s
[22:47:26] STDOUT:

[22:47:26] CMD: alembic current
[22:47:27] SUCCESS after 1.19s
[22:47:27] STDOUT:
7aa5b3a25e41 (head)

[22:47:27] SECTION: Seeding
[22:47:27] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[22:48:21] SUCCESS after 54.27s
[22:48:21] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=8 created=8 updated=0 skipped=0
  creditprogramdefinition: row_count=4 created=4 updated=0 skipped=0
  plan: row_count=5 created=5 updated=0 s...
[22:48:21] SECTION: Verification
[22:48:21] CMD: python -m scripts.verify_seed_schema_completeness
[22:48:23] SUCCESS after 1.37s
[22:48:23] STDOUT (snippet):
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
      "upload",
      "ocrchoice",
      "voicejob",
      "canonicalsolution",
 ...
[22:48:23] SECTION: Smoke Tests
[22:48:23] CMD: pytest tests/seeding/ -q
[22:48:45] SUCCESS after 21.89s
[22:48:45] STDOUT:
....                                                                     [100%]
4 passed in 20.23s

[22:48:45] Running smoke tests...
[22:48:45] CMD: pytest tests/smoke/ -q
[22:49:21] SUCCESS after 36.65s
[22:49:21] STDOUT (snippet):
........                                                                 [100%]
=============================== warnings summary ===============================
tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
tests/smoke/test_admin_rbac.py::test_admin_rbac_enforcement
  /app/app/auth.py:38: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(date...
[22:49:21] SECTION: Generating Report
... (see console for full logs)
```
