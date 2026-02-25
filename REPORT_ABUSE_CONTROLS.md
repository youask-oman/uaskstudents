# REPORT: WhatsApp Anti-Abuse Controls

## Implemented Modules
- `backend/app/services/whatsapp/anti_abuse.py`
  - layered rate limiting (user/phone/ip/global + solve/ocr/global)
  - daily and burst quotas
  - abuse score with time decay
  - confirmation gate (`YES`) for elevated abuse score
  - lock escalation ladder and phone/user locks
  - CODE brute-force protection
  - relink churn protection
  - circuit breakers and realtime counters
  - audit trail for admin actions

## Ingress Enforcement
- `backend/app/api.py` (`/api/v1/whatsapp/message`)
  - anti-abuse checks now run before enqueue:
    - lock check
    - layered rate limits
    - queue backpressure + OCR queue guard
    - quota checks
    - abuse score / confirmation / lock escalation
    - circuit breakers (`disable_solve`, `disable_media`)
  - all drop paths return user-friendly messages and (when relevant) `retry_after_seconds`
  - extreme repeated offenses can disable `whatsapp_enabled`

## Admin Endpoints
- `backend/app/api_admin.py`
  - `GET /api/admin/whatsapp/abuse/overview`
  - `GET /api/admin/whatsapp/abuse/locks`
  - `POST /api/admin/whatsapp/abuse/lock`
  - `DELETE /api/admin/whatsapp/abuse/lock`
  - `POST /api/admin/whatsapp/abuse/circuit`
  - `GET /api/admin/whatsapp/abuse/audit`

## Admin Dashboard Access
- `src/app/admin/whatsapp-monitor/page.tsx`
  - new anti-abuse control panel
  - live counters, top offenders, active locks, audit trail
  - emergency circuit toggles
  - manual force-lock and clear-lock tools
  - inline descriptions for each functionality

## Next.js Secure Proxy Routes
- `src/app/api/admin/whatsapp/abuse/overview/route.ts`
- `src/app/api/admin/whatsapp/abuse/locks/route.ts`
- `src/app/api/admin/whatsapp/abuse/lock/route.ts`
- `src/app/api/admin/whatsapp/abuse/circuit/route.ts`
- `src/app/api/admin/whatsapp/abuse/audit/route.ts`

## Tests Added
- `backend/tests/test_whatsapp_quota.py`
- `backend/tests/test_whatsapp_abuse.py`
- `backend/tests/test_whatsapp_lockouts.py`

## Environment Variables
- `WHATSAPP_QUOTA_SOLVES_PER_DAY`
- `WHATSAPP_QUOTA_OCR_PER_DAY`
- `WHATSAPP_QUOTA_SOLVES_PER_10M`
- `WHATSAPP_ABUSE_SCORE_THRESHOLD_WARN`
- `WHATSAPP_ABUSE_SCORE_THRESHOLD_LOCK`
- `WHATSAPP_LOCK_5M_THRESHOLD`
- `WHATSAPP_LOCK_1H_THRESHOLD`
- `WHATSAPP_DISABLE_THRESHOLD`
- `WHATSAPP_MAX_INVALID_CODE_ATTEMPTS_10M`
- `WHATSAPP_MAX_PHONE_CHANGES_PER_DAY`
- `WHATSAPP_MAX_OCR_QUEUE_DEPTH`
- `WHATSAPP_RL_IP_RPS`
- `WHATSAPP_RL_IP_BURST`
- `WHATSAPP_RL_GLOBAL_INBOUND_RPS`
- `WHATSAPP_RL_GLOBAL_INBOUND_BURST`
- `WHATSAPP_RL_SOLVE_USER_RPS`
- `WHATSAPP_RL_SOLVE_USER_BURST`
- `WHATSAPP_RL_GLOBAL_SOLVE_RPS`
- `WHATSAPP_RL_GLOBAL_SOLVE_BURST`
- `WHATSAPP_RL_OCR_USER_RPS`
- `WHATSAPP_RL_OCR_USER_BURST`
- `WHATSAPP_RL_GLOBAL_OCR_RPS`
- `WHATSAPP_RL_GLOBAL_OCR_BURST`

## Operational Notes
- All anti-abuse logic is deterministic and Redis-backed.
- Enforcement is fast-path and pre-enqueue to protect cost.
- No secrets/signatures are logged.
