# Solve Flow Endpoints

- `POST /api/v1/solve_v3_stream`
  - Main streaming solve endpoint used by `src/app/solve/page.tsx`.
  - Creates `request_id`/`attempt_id`, emits SSE (`meta`, `stage`, `delta`, `telemetry`, `done`), persists session/messages.

- `POST /api/v1/solve_v3`
  - Non-stream solve endpoint.
  - In current config (`SOLVE_V3_USE_SUPERSET_V2=true`) delegates to `run_solve_v3_superset_v2` and returns final JSON payload directly.

- `GET /api/v1/solve_v3_runtime_meta`
  - Returns runtime metadata from latest attempt or by explicit `attempt_id` / `request_id`.

- `POST /api/v1/solve/clarify`
  - Clarification follow-up path for ambiguous solves.

- `GET /api/v1/attempt/{attempt_id}`
  - Attempt status/details including runtime_meta and billing snapshots.

- `GET /api/v1/attempt/{attempt_id}/events`
  - SSE channel for attempt progress phase updates.

- `GET /api/v1/sessions/{session_id}`
  - Chat/session payload consumed by `/chat/[id]` UI, including assistant `structured_data` (steps, verification, visuals).

- `POST /api/v1/sessions/{session_id}/chat`
  - Follow-up chat turn endpoint tied to an existing session.

- `POST /api/v1/followup/{solve_session_id}`
  - Follow-up solve-session endpoint for post-solve conversation features.
