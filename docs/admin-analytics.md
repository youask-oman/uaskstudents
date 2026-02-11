# Admin Analytics Definitions

## Scope
- Audience: admins only.
- PII: aggregated metrics only. User drill-downs should show `user_id` without names/emails.

## Time Windows
- Default range: 7 days (`range=7d`). Supported: `7d`, `30d`.
- "Today" = last 24 hours from `utcnow`.
- "Online now" = `last_active_at` within last 5 minutes.

## Metric Definitions
- Student: `User.role == "student"` (if role missing, treat as student by default).
- Question: a solve request recorded as `RequestEvent` (cached or not).
- Active students today: unique `RequestEvent.user_id` in last 24 hours.
- Tokens today: sum of `RequestEvent.tokens_in` and `RequestEvent.tokens_out` in last 24 hours.
- Cost: `RequestEvent.cost_usd` when available; otherwise estimated from `tokens_total` and `OPENAI_COST_PER_1M_TOKENS`.
- Credit deductions: count of `UsageLedger` rows with `transaction_type == "DEBIT"` in last 24 hours.
- Deduction failures: `RequestEvent.status == "ok"` and `credit_deducted == False` and `is_cached == False`.
- Verified pass rate: `RequestEvent.verification_pass == True` divided by total requests.
- Schema violation rate: `RequestEvent.schema_valid == False` divided by total requests with `schema_valid` set.
- Streaming disconnect rate: `RequestEvent.is_stream == True` and `status == "error"`.

## Endpoints
- `GET /api/v1/admin/analytics/overview?range=7d|30d`
- `GET /api/v1/admin/analytics/errors?range=1d&severity=low|medium|high`
- `GET /api/v1/admin/analytics/anomalies?range=1d`

## Data Sources
- `RequestEvent`: core analytics source (mode, model, tokens, cost, latency, status).
- `UsageLedger`: credit deduction counts.
- `OCRJob`: OCR failure reasons.
- `User`: total users, online now, new users.

## Notes
- The overview response is cached for 60 seconds in process.
- For accurate cost, set `MODEL_PRICING_PER_MILLION` (JSON map of model -> {input, output}) and optionally `OPENAI_COST_PER_1M_TOKENS` as a fallback.

Example:
```json
{
  "gpt-4o": { "input": 5.0, "output": 15.0 },
  "gpt-5-mini": { "input": 0.15, "output": 0.60 }
}
```
