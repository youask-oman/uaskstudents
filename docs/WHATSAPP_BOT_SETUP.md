# WhatsApp Bot Setup (Secure Path)

## 1) Configure secrets
Set the same signing secret in both backend and WhatsApp Node bridge runtime:

```env
WHATSAPP_SIGNING_SECRET=change-me-strong-random
WHATSAPP_INTERNAL_KEY=internal-channel-key
```

The bridge signs inbound `/api/v1/whatsapp/message` and `/api/v1/whatsapp/media` requests.

## 2) Start services
```bash
docker compose up -d redis orchestrator worker
```

## 3) Initialize bot (admin-authenticated)
Use an admin JWT in `Authorization: Bearer <token>`:

```bash
curl -X POST http://127.0.0.1:9000/api/admin/whatsapp/initialize \
  -H "Authorization: Bearer <admin_jwt>"
```

## 4) Verify admin monitoring
```bash
curl http://127.0.0.1:9000/api/admin/whatsapp/monitor \
  -H "Authorization: Bearer <admin_jwt>"
```

The response includes:
- bot status
- celery/whatsapp queue depth
- ingress protection counters (signature fail, replay reject, rate-limited, dedup hit, enqueue stats)
- anti-abuse telemetry (inbound/enqueued/dropped counters and top offenders) via `/api/admin/whatsapp/abuse/overview`

## 5) User linking flow
- User sends `CODE XXXXXXXX` to bot.
- Backend matches `User.whatsapp_secret` and binds `whatsapp_number`.
- If `whatsapp_enabled=false`, ingress returns disabled response and does not enqueue.

## 6) Rotation note
Assume prior `whatsapp_secret` exposure risk from legacy profile endpoint:
- rotate all user WhatsApp secrets at controlled rollout windows
- notify users to relink once
- do not expose raw secret in profile responses

## 7) Worker tuning
Celery worker concurrency is controlled at process start (example):
```bash
celery -A app.worker.celery_app worker -Q whatsapp,celery --concurrency=8
```

Task-level per-minute limits still apply:
- `WHATSAPP_SOLVE_RATE_LIMIT`
- `WHATSAPP_OCR_RATE_LIMIT`

## 8) Anti-abuse admin operations
All secured behind admin auth:
- `GET /api/admin/whatsapp/abuse/overview`
- `GET /api/admin/whatsapp/abuse/locks`
- `POST /api/admin/whatsapp/abuse/lock`
- `DELETE /api/admin/whatsapp/abuse/lock`
- `POST /api/admin/whatsapp/abuse/circuit`
- `GET /api/admin/whatsapp/abuse/audit`

Use circuit flags for emergency traffic shaping:
- `wa:circuit:disable_solve=1` pauses solve enqueue
- `wa:circuit:disable_media=1` pauses media/OCR enqueue
