# Admin Dashboard Test Report
    
**Date:** 2026-02-09T22:50:04.808027+00:00  
**Status:** SUCCESS

## 1. Inventory Summary
- **Admin UI Pages:** 30
- **Admin Backend Endpoints:** 135

## 2. API Test Results
- **Passed:** 77
- **Failed:** 0
- **Avg Response Time:** 18.39ms
- **P95 Response Time:** 25.27ms

### Top Failures
None! All tested endpoints returned 200/404/valid JSON.

## 3. Discovered UI Pages (Tabs)
- /admin/billing
- /admin/billing/flags
- /admin/billing/health
- /admin/billing/holds
- /admin/billing/invoices
- /admin/billing/ledger
- /admin/billing/programs
- /admin/billing/programs/enrollments
- /admin/billing/refunds
- /admin/billing/users/[userId]/wallet
- /admin/content
- /admin/dashboard
- /admin/data
- /admin/logs
- /admin/prompt-bindings
- /admin/prompt-registry
- /admin/prompts
- /admin/quotas
- /admin/schema-registry
- /admin/social-logs
- /admin/solver-attempts
- /admin/subscriptions
- /admin/system-config
- /admin/users
- /admin/users/[id]
- /admin/whatsapp-bot
- /admin/whatsapp-monitor
- /adminpayments
- /adminpayments/requests
- /adminpayments/topups

## 4. Pytest Output Summary
```
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-9.0.2, pluggy-1.6.0 -- /usr/local/bin/python3.13
cachedir: .pytest_cache
rootdir: /app
configfile: pytest.ini
plugins: asyncio-1.3.0, anyio-4.12.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 3 items

tests/smoke/test_admin_rbac.py::test_admin_rbac_enforcement PASSED       [ 33%]
tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200 PASSED   [ 66%]
tests/smoke/test_admin_pages_all.py::test_admin_ui_routes_exist PASSED   [100%]

=============================== warnings summary ===============================
tests/smoke/test_admin_rbac.py::test_admin_rbac_enforcement
tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/auth.py:38: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    expire = datetime.utcnow() + expires_delta

tests/smoke/test_admin_rbac.py::test_admin_rbac_enforcement
tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /home/appuser/.local/lib/python3.13/site-packages/httpx/_client.py:680: DeprecationWarning: The 'app' shortcut is now deprecated. Use the explicit style 'transport=WSGITransport(app=...)' instead.
    warnings.warn(message, DeprecationWarning)

tests/smoke/test_admin_rbac.py: 19 warnings
tests/smoke/test_admin_api_all.py: 66 warnings
  /usr/local/lib/python3.13/site-packages/jose/jwt.py:311: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = timegm(datetime.utcnow().utctimetuple())

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api.py:958: DeprecationWarning: 
          🚨 `obj.dict()` was deprecated in SQLModel 0.0.14, you should
          instead use `obj.model_dump()`.
          
    data = obj.dict()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api.py:7990: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/services/admin/analytics_service.py:182: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/services/admin/analytics_service.py:494: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/services/admin/analytics_service.py:529: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api.py:8341: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api.py:9127: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    cutoff = datetime.utcnow() - timedelta(minutes=15)

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api_admin_payments.py:24: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api_admin_health.py:44: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    "timestamp": datetime.utcnow().isoformat(),

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api_admin_health.py:118: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    cutoff = datetime.utcnow() - timedelta(hours=hours)

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api_admin_health.py:158: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    cutoff = datetime.utcnow() - timedelta(hours=hours)

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/api_admin_health.py:227: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/jobs/nightly_reconciliation.py:56: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/admin_billing/billing_holds.py:76: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/admin_billing/billing_holds.py:153: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

tests/smoke/test_admin_api_all.py::test_admin_api_endpoints_200
  /app/app/admin_billing/billing_health.py:58: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 3 passed, 105 warnings in 27.87s =======================
```
