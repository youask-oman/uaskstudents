# Implemented Recommendation Checklist

Date: 2026-02-14

## Completed In Code

1. Tighten first-pass reliability (not verbosity)
- Added schema contract optimizer for model calls and validation parity.
- Files:
  - `backend/app/utils/solve_schema_contract.py`
  - `backend/app/services/solver_v3.py`
  - `backend/app/api.py`

2. Add enum-safe micro-instructions (difficulty, detected_tasks)
- Added automatic enum-safety prompt augmentation before LLM call.
- File: `backend/app/services/solver_v3.py`

3. Simplify required schema fields
- Removed backend-only/noisy required fields from model contract via schema optimization.
- File: `backend/app/utils/solve_schema_contract.py`

4. Make `_raw_llm_output` / debug/runtime backend-only (for model output)
- Model-facing schema now treats these as non-required backend-managed fields.
- Files:
  - `backend/app/utils/solve_schema_contract.py`
  - `backend/app/services/solver_v3.py`

5. Reduce nullable boilerplate fields the model fills with noise
- Nullable noise required fields are dropped in model-facing contract.
- File: `backend/app/utils/solve_schema_contract.py`

6. Split schemas by response kind
- Added lightweight response-kind branch contract (`solution` / `clarification` / `refusal`) using `oneOf` constraints.
- File: `backend/app/utils/solve_schema_contract.py`

7. Normalize enum sets across tiers
- Normalization map fixes for tasks/grade_band/difficulty.
- Backend detected_tasks inference to reduce model drift.
- Files:
  - `backend/app/services/response_mapper.py`
  - `backend/app/services/solver_v3.py`

8. Deterministic backend enrichment
- Deterministic plot generation from recipe/domain/key_points.
- Backend-side compactness enforcement by tier for steps/explanations.
- Files:
  - `backend/app/services/plot_integration.py`
  - `backend/app/services/response_mapper.py`

9. Prompt improvements
- Prompt duplication suppression between system/developer.
- Enum safety and backend-only field guidance injected as compact delta.
- File: `backend/app/services/solver_v3.py`

10. Remove giant schema text duplication in prompt body
- Repair flow no longer embeds full schema text in prompt body.
- File: `backend/app/services/solver_v3.py`

11. Conditional repair pass
- Repair remains conditional; second pass is env-gated (`SOLVE_V3_SECOND_REPAIR_PASS`).
- File: `backend/app/api.py`

12. Plot: disable LLM plot-spec path by default and use deterministic renderer
- Implemented earlier and kept.
- File: `backend/app/services/plot_integration.py`

## Additional Hardening
- Validation now uses same optimized contract as model output path to avoid false repair loops.
- File: `backend/app/api.py`

## Verification
- Syntax checks passed:
  - `backend/app/utils/solve_schema_contract.py`
  - `backend/app/services/solver_v3.py`
  - `backend/app/services/response_mapper.py`
  - `backend/app/api.py`
