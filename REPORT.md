# WhatsApp Hardening Report

## Scope implemented
- Hardened admin WhatsApp controls and unified secure namespace usage (`/api/admin/whatsapp/*`).
- Added signed ingress authentication for Node->backend message path.
- Added replay protection, rate limiting, dedup, payload caps, and queue-depth backpressure.
- Refactored inbound solve to queue-only path.
- Removed profile response secret leakage and enforced auth/self-only profile/preferences updates.
- Added tests and local 100-concurrency load harness.

## A-I investigation answers

### A) Is `/api/v1/whatsapp/message` internal-only?
No. In `docker-compose.yml`, orchestrator maps `9000:8000`, and Uvicorn binds `0.0.0.0:8000`, so the route is reachable from host/public network where port 9000 is exposed.

### B) Does Next admin use sessions/JWT? where validated?
It used client-stored JWT (`localStorage token`) with weak client-side role checks and proxy routes that previously forwarded without auth. Minimal secure approach implemented:
- Next WhatsApp admin proxy now requires bearer auth (or server-only `ADMIN_SERVICE_BEARER_TOKEN`) in `src/app/api/admin/whatsapp/_proxy.ts`
- Proxy forwards bearer to backend `/api/admin/whatsapp/*`.

### C) Where is `require_admin` equivalent defined? used by `api_admin.py`?
Equivalent is `get_admin_user` in:
- `backend/app/api_admin.py` (admin/devops/superadmin)
- `backend/app/admin_billing/deps.py` (admin/superadmin)
`api_admin.py` WhatsApp routes now use `Depends(get_admin_user)`.

### D) How does Node call backend endpoints? env secret access?
Node bridge script is generated in `backend/app/services/whatsapp/whatsapp_service.py` and calls backend with `fetch` to:
- `/api/v1/whatsapp/media`
- `/api/v1/whatsapp/message`
It has env access (including internal key/signing secret) because the script runs as subprocess in orchestrator environment.

### E) Existing internal key mechanism for `/whatsapp/media`? where validated?
Validated in backend `upload_whatsapp_media` by `X-UASK-INTERNAL-KEY` against `WHATSAPP_INTERNAL_KEY`. Bridge already sent this for `/whatsapp/media`; now signature headers are also attached/validated.

### F) Existing `WHATSAPP_SOLVE_RATE_LIMIT`/`WHATSAPP_OCR_RATE_LIMIT`? where enforced?
Configured in Celery task annotations in `backend/app/worker.py` for tasks:
- `whatsapp_solve`
- `whatsapp_ocr_extract`
This is worker-side throttling, not ingress protection. Ingress RL was added separately.

### G) Synchronous solve path for text?
Previously in `backend/app/api.py` `/whatsapp/message`, text path called `solver_service.solve_problem(...)` inline. Refactored to queue-only (`celery_app.send_task("whatsapp_solve", ...)`).

### H) User linking algorithm (`whatsapp_number`, `whatsapp_secret`, CODE flow)?
In `/api/v1/whatsapp/message`: message text matching `CODE XXXXXXXX` is looked up by `User.whatsapp_secret`; on success it sets `user.whatsapp_number = normalized_number`. This remains in place.

### I) Is WhatsApp message id available inbound today?
Yes. Bridge uses Baileys `msg.key.id` and sends `message_id`. Dedup now uses Redis key `wa:dedup:{message_id}` before enqueue.

## Verification checklist
- [ ] Missing/invalid signature on `/api/v1/whatsapp/message` returns 401.
- [ ] Replay nonce returns 409.
- [ ] Drifted timestamp rejected.
- [ ] Duplicate `message_id` is ACK-only and not enqueued twice.
- [ ] `whatsapp_enabled=false` blocks enqueue.
- [ ] Rate-limited requests return friendly throttle.
- [ ] Queue depth over threshold returns busy response.
- [ ] `/api/admin/whatsapp/*` rejects unauthenticated calls.
- [ ] `/api/v1/admin/whatsapp/*` legacy paths are admin-guarded.
- [ ] `/user/profile` response no longer includes `whatsapp_secret`.
- [ ] `/user/profile` and `/user/preferences` are auth + self-only.

## Run commands

### Tests
```bash
pytest backend/tests/test_whatsapp_security.py -q
pytest backend/tests/test_whatsapp_admin.py -q
pytest backend/tests/test_whatsapp_ingress_protections.py -q
pytest backend/tests/test_whatsapp_queue.py -q
```

### Load test (100 concurrent)
```bash
python tools/loadtest_whatsapp_inbound.py \
  --url http://127.0.0.1:9000/api/v1/whatsapp/message \
  --secret "$WHATSAPP_SIGNING_SECRET" \
  --total 100 \
  --concurrency 100
```
