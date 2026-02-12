# Solve Pipeline V2

`/api/v1/solve_v3` now supports a DB-configured Superset v2 flow with mandatory SymPy verification.

## Active Config (DB keys)

- `SOLVE_SYSTEM_PROMPT_ID`
- `SOLVE_ORCHESTRATOR_DEV_PROMPT_ID`
- `SOLVE_OUTPUT_CONTRACT_ID`
- `SOLVE_NARRATOR_PROMPT_ID`
- `SOLVE_PLOT_SPEC_PROMPT_ID`
- `SOLVE_REPAIR_PROMPT_ID`
- `SOLVE_CLARIFY_PROMPT_ID`
- `SOLVE_SCHEMA_ID`
- `SOLVE_TIER_POLICY_JSON`
- `SOLVE_NARRATOR_ENABLED`
- `SOLVE_V3_USE_SUPERSET_V2`

Admin endpoints:

- `GET /api/v1/admin/solve-v2-config`
- `POST /api/v1/admin/solve-v2-config`

## Request Flow

1. Intake and create `SolverOutputAttempt` (`status=processing`) before LLM calls.
2. Detect multi-question inputs.
3. Canonicalize (`sympy_canonicalization`) and check canonical cache.
4. Run orchestrator prompt + output contract against `solve_superset_v2.schema.json`.
5. Validate JSON schema; perform one schema-repair pass if needed.
6. If multi-question is detected, run clarification prompt and return `response_kind=clarification` (single-question policy).
7. Run SymPy verification gate and overwrite verification fields.
8. If verification fails for a verifiable equation task, do one verification-repair LLM pass and re-verify.
9. Optionally run narrator style pass for `STANDARD/RESEARCH` when enabled, while protecting math fields.
10. Run plot integration and normalize plot output into Superset v2 visuals fields.
11. Persist final attempt state and return controlled payload.

## Response Guarantees

- Verification metadata is always present under `verification`.
- `verified` is derived from backend verification gate only.
- Runtime timing is under `runtime_meta.timing_ms`.
- Controlled errors return `failed_controlled` payloads with `request_id` and `attempt_id`.

## Notes

- `solve_v3_stream` remains separate.
- Superset v2 route can be toggled via `SOLVE_V3_USE_SUPERSET_V2`.
- Production seeding now includes `seed_data/solve_superset_v2_bundle.json` and `seed_production.py` merges it into prompt/schema seeds.
