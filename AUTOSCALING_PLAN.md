# WhatsApp Autoscaling Plan

## Current hooks implemented now
- Ingress backpressure: `WHATSAPP_MAX_QUEUE_DEPTH` rejects new enqueue when queue is overloaded.
- Ingress counters in Redis (`wa:metrics:*`) for drops/failures/successes.
- Admin monitor includes ingress metrics + queue depth.
- Worker task processing is fully async from ingress (queue-only solve path).

## Local scale strategy
1. Scale workers by queue:
```bash
docker compose up -d --scale worker=2
```
2. Increase worker concurrency when CPU/memory permits:
```bash
celery -A app.worker.celery_app worker -Q whatsapp,celery --concurrency=8
```
3. Keep ingress `WHATSAPP_MAX_QUEUE_DEPTH` conservative so API ACK stays fast.

## Production strategy (next phase)
1. Move workers to Kubernetes Deployment.
2. Export queue depth + processing latency as Prometheus metrics.
3. HPA policy:
- scale on `whatsapp_queue_depth`
- scale on worker CPU
- optional scale on `wa:metrics:busy_reject` / rate-limited trend
4. Keep dedup/idempotency keys in shared Redis.
5. Add DLQ (dead-letter queue) for repeatedly failing tasks.

## Recommended SLOs
- Ingress ACK p95 < 300ms at 100 concurrent inbounds.
- Queue wait p95 < 5s for normal load.
- Worker failure rate < 1%.
