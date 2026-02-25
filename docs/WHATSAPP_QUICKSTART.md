# WhatsApp Integration Quickstart (Hardened)

## Required env
- `WHATSAPP_SIGNING_SECRET` (required; shared between Node bridge and FastAPI)
- `WHATSAPP_INTERNAL_KEY` (still used for internal send/media server auth)
- `WHATSAPP_SIGNATURE_MAX_DRIFT_SECONDS` (default `300`)
- `WHATSAPP_RL_USER_RPS`, `WHATSAPP_RL_USER_BURST`
- `WHATSAPP_RL_PHONE_RPS`, `WHATSAPP_RL_PHONE_BURST`
- `WHATSAPP_MAX_TEXT_CHARS` (default `4000`)
- `WHATSAPP_MAX_MEDIA_COUNT` (default `1`)
- `WHATSAPP_MAX_METADATA_BYTES` (default `65536`)
- `WHATSAPP_MAX_QUEUE_DEPTH` (default `1000`)
- `WHATSAPP_QUOTA_SOLVES_PER_DAY`, `WHATSAPP_QUOTA_OCR_PER_DAY`, `WHATSAPP_QUOTA_SOLVES_PER_10M`
- `WHATSAPP_ABUSE_SCORE_THRESHOLD_WARN`, `WHATSAPP_ABUSE_SCORE_THRESHOLD_LOCK`
- `WHATSAPP_LOCK_5M_THRESHOLD`, `WHATSAPP_LOCK_1H_THRESHOLD`, `WHATSAPP_DISABLE_THRESHOLD`
- `WHATSAPP_MAX_INVALID_CODE_ATTEMPTS_10M`, `WHATSAPP_MAX_PHONE_CHANGES_PER_DAY`
- `WHATSAPP_RL_SOLVE_USER_RPS`, `WHATSAPP_RL_SOLVE_USER_BURST`
- `WHATSAPP_RL_OCR_USER_RPS`, `WHATSAPP_RL_OCR_USER_BURST`
- `WHATSAPP_RL_GLOBAL_INBOUND_RPS`, `WHATSAPP_RL_GLOBAL_INBOUND_BURST`
- `WHATSAPP_RL_GLOBAL_SOLVE_RPS`, `WHATSAPP_RL_GLOBAL_SOLVE_BURST`
- `WHATSAPP_RL_GLOBAL_OCR_RPS`, `WHATSAPP_RL_GLOBAL_OCR_BURST`
- `WHATSAPP_RL_IP_RPS`, `WHATSAPP_RL_IP_BURST` (used only when client IP is available)
- `WHATSAPP_MAX_OCR_QUEUE_DEPTH`

## What changed
- Inbound `/api/v1/whatsapp/message` now requires HMAC signature + timestamp + nonce replay protection.
- Inbound solve path is queue-only (no synchronous solve/OCR in API request path).
- Ingress adds dedup, token-bucket rate limiting, payload caps, and queue-depth backpressure.
- Ingress now adds anti-abuse controls: quotas, abuse score + decay, lock escalation, and confirmation gates.
- Admin has abuse controls in `/admin/whatsapp-monitor`: circuit toggles, force/clear lock, offender list, and audit trail.
- Legacy `/api/v1/admin/whatsapp/*` routes are now admin-protected.
- Canonical admin namespace is `/api/admin/whatsapp/*`.
- Profile response no longer exposes `whatsapp_secret`; profile/preferences are auth + self-only.

## Local run
```bash
docker compose up -d redis orchestrator worker
```

## Security smoke checks
```bash
# should fail (missing signature)
curl -i -X POST http://127.0.0.1:9000/api/v1/whatsapp/message -H "content-type: application/json" -d "{}"

# admin endpoint should fail without bearer
curl -i http://127.0.0.1:9000/api/admin/whatsapp/status
```

## Targeted tests
```bash
pytest backend/tests/test_whatsapp_security.py -q
pytest backend/tests/test_whatsapp_admin.py -q
pytest backend/tests/test_whatsapp_ingress_protections.py -q
pytest backend/tests/test_whatsapp_queue.py -q
```

## 100-concurrency local load
```bash
python tools/loadtest_whatsapp_inbound.py --secret "$WHATSAPP_SIGNING_SECRET" --total 100 --concurrency 100
```
