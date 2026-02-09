# DEV Database Recreate & Seed Log

**Date:** 2026-02-09T22:13:55.146733+00:00  
**Status:** SUCCESS  
**Alembic Revision:** `25e7fcf4d1c5 (head)`

## 1. Execution Summary
Refreshed DEV database with full production seed dataset + DEV fixtures.

## 2. Row Counts
| Table | Count | Expected | Status |
|---|---|---|---|
| `school` | N/A | N/A | OK |
| `prompt_templates` | N/A | - | OK |
| `prompt_bindings` | N/A | - | OK |
| `json_schemas` | N/A | - | OK |
| `user (internal)` | N/A | 10 | OK |

## 3. Forbidden Tables (Must be 0)
{}

## 4. Integrity Check
Result: Unknown

## 5. Logs
```
[22:12:15] SECTION: Preflight Check
[22:12:15] SECTION: Nuke DB
[22:12:15] Truncating 70 tables...
[22:12:17] SECTION: Migrations
[22:12:17] CMD: alembic upgrade head
[22:12:18] SUCCESS after 1.27s
[22:12:18] STDOUT:

[22:12:18] CMD: alembic current
[22:12:19] SUCCESS after 1.16s
[22:12:19] STDOUT:
25e7fcf4d1c5 (head)

[22:12:19] SECTION: Seeding
[22:12:19] CMD: python -m scripts.seed_production --env DEV --dev-fixtures
[22:13:12] SUCCESS after 52.83s
[22:13:12] STDOUT (snippet):
Seed completed:
  systemconfig: row_count=30 created=30 updated=0 skipped=0
  json_schemas: row_count=8 created=8 updated=0 skipped=0
  prompt_templates: row_count=10 created=10 updated=0 skipped=0
  prompt_schema_links: row_count=0 created=0 updated=0 skipped=0
  prompt_bindings: row_count=9 created=9 updated=0 skipped=0
  providermodelpricing: row_count=8 created=8 updated=0 skipped=0
  creditprogramdefinition: row_count=4 created=8 updated=0 skipped=0
  plan: row_count=4 created=0 updated=0 s...
[22:13:12] SECTION: Verification
[22:13:12] CMD: python -m scripts.verify_seed_schema_completeness
[22:13:13] SUCCESS after 1.31s
[22:13:13] STDOUT (snippet):
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
      "ocrextractioncache",
      "json_schemas",
      "ocrchoice",
      "ocrqu...
[22:13:13] SECTION: Smoke Tests
[22:13:13] CMD: pytest tests/seeding/ -q
[22:13:35] SUCCESS after 22.01s
[22:13:35] STDOUT:
....                                                                     [100%]
4 passed in 20.28s

[22:13:35] Running advisory smoke tests (failures logged but not blocking)...
[22:13:35] CMD: pytest tests/smoke/ -q
[22:13:53] FAILED (code 1) after 17.95s
[22:13:53] STDOUT:
.F                                                                       [100%]
=================================== FAILURES ===================================
_____________________ test_schema_driven_endpoints_no_500s _____________________

    def test_schema_driven_endpoints_no_500s():
        os.environ["APP_ENV"] = "DEV"
        os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
        run_seed(app_env="DEV", rotate_passwords=False, dev_fixtures=False)
    
        _resolve_modes()
        user_id = _ensure_user()
        client = TestClient(app)
    
        fake_solver = MagicMock()
        fake_solver.solve = AsyncMock(
            return_value={
                "solution": {"final_answer": "ok"},
                "telemetry": {"prompt_binding": {"global_system_prompt_id": "x", "developer_prompt_id": "y"}},
            }
        )
        with patch("app.services.solver_v3.get_solver_v3", return_value=fake_solver):
            for tier in ("standard", "research"):
                resp = client.post(
                    "/api/v1/solve",
                    json={"text": "What is 2+2?", "tier": tier, "requested_mode": "text"},
                    headers={"X-User-ID": str(user_id)},
                )
>               assert resp.status_code != 500, f"{tier} solve returned 500: {resp.text}"
E               AssertionError: standard solve returned 500: {"detail":"404: User not found"}
E               assert 500 != 500
E                +  where 500 = <Response [500 Internal Server Error]>.status_code

tests/smoke/test_schema_driven_endpoints.py:62: AssertionError
----------------------------- Captured stderr call -----------------------------
INFO:api:Incoming: POST /api/v1/solve
Traceback (most recent call last):
  File "/app/app/api.py", line 3794, in solve_problem
    raise HTTPException(status_code=404, detail="User not found")
fastapi.exceptions.HTTPException: 404: User not found
Traceback (most recent call last):
  File "/app/app/api.py", line 3794, in solve_problem
    raise HTTPException(status_code=404, detail="User not found")
fastapi.exceptions.HTTPException: 404: User not found
INFO:api:Response: 500 | 18ms
------------------------------ Captured log call -------------------------------
INFO     api:main.py:50 Incoming: POST /api/v1/solve
INFO     api:main.py:58 Response: 500 | 18ms
=============================== warnings summary ===============================
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_schema_driven_endpoints.py::test_schema_driven_endpoints_no_500s
  /home/appuser/.local/lib/python3.13/site-packages/httpx/_client.py:690: DeprecationWarning: The 'app' shortcut is now deprecated. Use the explicit style 'transport=WSGITransport(app=...)' instead.
    warnings.warn(message, DeprecationWarning)

tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
  /app/app/auth.py:40: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

tests/smoke/test_admin_routes.py: 16 warnings
  /usr/local/lib/python3.13/site-packages/jose/jwt.py:311: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = timegm(datetime.utcnow().utctimetuple())

tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
  /app/app/jobs/nightly_reconciliation.py:56: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
  /app/app/admin_billing/billing_holds.py:76: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
  /app/app/admin_billing/billing_health.py:58: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_admin_routes.py::test_admin_billing_routes_access_matrix
tests/smoke/test_schema_driven_endpoints.py::test_schema_driven_endpoints_no_500s
tests/smoke/test_schema_driven_endpoints.py::test_schema_driven_endpoints_no_500s
tests/smoke/test_schema_driven_endpoints.py::test_schema_driven_endpoints_no_500s
  /usr/local/lib/python3.13/site-packages/pydantic/fields.py:747: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return fac()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/smoke/test_schema_driven_endpoints.py::test_schema_driven_endpoints_no_500s
1 failed, 1 passed, 31 warnings in 14.54s

[22:13:53] STDERR:

[22:13:53] WARNING: Some smoke tests failed. These are advisory and do not block the workflow.
[22:13:53] Review the output above for details. Common known issues:
[22:13:53]   - test_schema_driven_endpoints: relies on full solver mock chain
[22:13:53]   - test_admin_routes: depends on all admin billing endpoints being stable
[22:13:53] SECTION: Generating Report
... (see console for full logs)
```
