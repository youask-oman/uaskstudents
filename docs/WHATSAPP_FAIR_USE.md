# WhatsApp Fair Use Policy

## Purpose
This policy protects all students from spam, abuse, and service degradation while keeping normal use smooth.

## Limits
- Message rate limits apply per user, phone, and globally.
- Solve and OCR requests have separate rate limits.
- Daily quotas apply for solves and OCR.
- Short-burst quotas apply (solves per 10 minutes).
- Payload caps apply (text length and media limits).

## Abuse Controls
- Repeated identical messages, greeting spam, repeated near-cap payloads, and media bursts increase an abuse score.
- High abuse score can require a manual confirmation step (`YES`) before continuing.
- Repeated violations trigger temporary lockouts (5 minutes, then 1 hour).
- Extreme repeated violations can automatically disable WhatsApp for that account.

## Pairing and Linking Protection
- Verification code attempts are capped per phone (10-minute window).
- Too many invalid CODE attempts trigger temporary phone lock.
- Phone relink churn is limited per user per day.

## Recovery Paths for Students
- Wait for cooldown and retry after the provided seconds.
- Continue from web/app if WhatsApp quota is reached.
- Contact support if lockouts continue unexpectedly.

## Admin Controls
- Emergency circuit breakers: disable solve and/or media lanes.
- Manual lock/clear lock actions by user or phone.
- Offender telemetry, realtime drop counters, and audit logs.
