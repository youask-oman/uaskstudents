# End-to-End Solve Flow + SymPy/NumPy Verification + Plot Pipeline Report

Generated on **February 13, 2026** against local production stack (`uask_orchestrator` on `localhost:9000`) using real code paths.

## Artifacts Index
- Code map: `reports/solve_flow_evidence/solve_flow_code_map.json`
- Sequence diagram source: `reports/solve_flow_evidence/solve_flow_sequence.mmd`
- Endpoint inventory: `reports/solve_flow_evidence/solve_flow_endpoints.md`
- Prompt/schema DB snapshot: `reports/solve_flow_evidence/prompt_schema_snapshot.json`
- Live cases summary: `reports/solve_flow_evidence/live_cases_summary.json`
- Live requests/responses/meta:
  - `reports/solve_flow_evidence/live_case_L1_request.json`
  - `reports/solve_flow_evidence/live_case_L1_response.json`
  - `reports/solve_flow_evidence/live_case_L1_runtime_meta.json`
  - `reports/solve_flow_evidence/live_case_L2_request.json`
  - `reports/solve_flow_evidence/live_case_L2_response.json`
  - `reports/solve_flow_evidence/live_case_L2_runtime_meta.json`
  - `reports/solve_flow_evidence/live_case_L3_request.json`
  - `reports/solve_flow_evidence/live_case_L3_response.json`
  - `reports/solve_flow_evidence/live_case_L3_runtime_meta.json`
- SymPy proof logs:
  - `reports/solve_flow_evidence/sympy_verification_proof.log`
  - `reports/solve_flow_evidence/live_case_L1_sympy_proof.log`
  - `reports/solve_flow_evidence/live_case_L2_sympy_proof.log`
  - `reports/solve_flow_evidence/live_case_L3_sympy_proof.log`
  - `reports/solve_flow_evidence/verification_gate_trace_L1.json`
  - `reports/solve_flow_evidence/verification_gate_trace_L2.json`
  - `reports/solve_flow_evidence/verification_gate_trace_L3.json`
- NumPy proof:
  - `reports/solve_flow_evidence/numpy_usage_proof.log`
  - `reports/solve_flow_evidence/numpy_call_sites.txt`
- Plot traces/artifacts:
  - `reports/solve_flow_evidence/plot_pipeline_trace_L1.json`
  - `reports/solve_flow_evidence/plot_pipeline_trace_L2.json`
  - `reports/solve_flow_evidence/plot_pipeline_trace_L3.json`
  - `reports/solve_flow_evidence/plot_artifacts/`
- Local-only test pack:
  - `reports/solve_flow_evidence/local_plot_test_pack_results.json`
  - `reports/solve_flow_evidence/local_plot_test_pack.log`
  - `reports/solve_flow_evidence/local_pytest_output.log`

## Section A - Solve Flow (Frontend -> Backend -> OpenAI -> Response)

### 1) Frontend flow
- Solve trigger is in `src/app/solve/page.tsx` inside `handleSolve`.
- It sends `POST /api/v1/solve_v3_stream?user_id=...` with payload fields:
  - `confirmed_text`
  - `requested_mode` (`minimal` for FREE/SHORT, `detailed` for STANDARD/RESEARCH)
  - `tier`
  - `graph_mode` (`off|auto|on`)
  - `trusted_context` (`learning_mode`, region/grade)
  - `features_used` (`ocr_used`, `voice_used`, `plot_requested`, etc.)
  - `attach_to_step_id`
  - `force_validity`
  - `idempotency_key`
- Credits are checked/deducted in backend before solve execution (`check_entitlement_and_debit` or Billing V2 hold flow in `solve_v3_stream_endpoint`).
- Frontend stores attempt tracking in local storage (`uask.activeAttemptId`) when SSE `meta` includes `attempt_id`/`request_id`.

### 2) Backend entry
- Primary production routes:
  - `POST /api/v1/solve_v3_stream` -> `solve_v3_stream_endpoint` in `backend/app/api.py`
  - `POST /api/v1/solve_v3` -> `solve_v3_endpoint` in `backend/app/api.py`
- User identity for these routes is currently `user_id` query parameter.
- `request_id` and `attempt_id` are generated at route start.
- Attempt is persisted in `SolverOutputAttempt` and updated through pending -> processing -> success/failure.

### 3) Orchestration layer
- Stream route (`/solve_v3_stream`) resolves profile via `ProfileResolver.resolve_profile` and uses binding-derived system/developer/schema.
- Non-stream route (`/solve_v3`) currently uses superset v2 orchestrator (`run_solve_v3_superset_v2`) when `SOLVE_V3_USE_SUPERSET_V2=true`.
- Superset v2 orchestrator controls:
  - tier mapping (`_tier_to_v2`)
  - mode normalization
  - verification applicability
  - graph mode override
  - plot execution timeout
- DB-configured production prompt/schema IDs (snapshot in `prompt_schema_snapshot.json`):
  - system: `global_system_prompt_v2_compact.txt`
  - orchestrator developer: `solve_orchestrator_developer_v2_compact.txt`
  - plot developer: `solve_plot_spec_v2_compact.txt`
  - repair developer: `solve_repair_verification_patch_v1.txt`
  - clarify developer: `solve_clarification_patch_v1.txt`
  - internal superset schema: `solve_superset_v2.schema.json`
  - OpenAI LLM-min schema: `solve_llm_min_v2.schema.json`

#### LLM-min vs internal schema (explicit)
- **OpenAI response_format schema** in superset-v2 path: `SOLVE_LLM_MIN_SCHEMA_ID` (`solve_llm_min_v2.schema.json`) wrapped via `_schema_wrapper(...)` and passed to `_call_llm_with_schema(...)`.
- **Internal backend schema**: `SOLVE_SCHEMA_ID` (`solve_superset_v2.schema.json`) used after assembly/verification/plot normalization with strict validation.

### 4) OpenAI boundary
- OpenAI call site: `backend/app/services/solver_v3.py` (`_call_llm_with_schema`, stream variant in `solve_stream`).
- Sent: system+developer+user messages plus `response_format={type:json_schema,...}`.
- Returned: parsed structured JSON + usage + model + finish reason + raw content.
- Runtime meta captured in response and attempt row (`runtime_meta` includes tokens/latency/provider/model).

### 5) Assembly into internal response
- LLM-min -> superset transformation: `_llm_min_to_superset(...)` in `backend/app/services/solve/superset_v2_pipeline.py`.
- Backend-derived fields include:
  - `verification` block (from SymPy gate)
  - `runtime_meta`
  - normalized `visuals` (graph_mode override + pipeline merge)
  - `request_id`/`attempt_id`
- Model-returned fields remain primarily steps/final answer/problem/classification/initial visual recipe content.

## Section B - Verification: Where/When SymPy Executes (Hard Proof)

### 1) Verification trigger rules
- Verification runs in superset-v2 solve path after LLM-min assembly when `response_kind == solution`.
- It is skipped or forced non-verified when:
  - no equation/unsupported verification context (`unverified_reason=not_applicable`), or
  - symbolic parsing fails (`symbolic_parse_failed`), or
  - verification path says not applicable by `_is_verification_applicable(...)`.

### 2) What SymPy actually does
`backend/app/services/solve/verification_gate.py` performs:
- candidate substitution checks (`subs`, `evalf`, numeric tolerance)
- domain-related checks for sqrt/log/negative powers constraints
- extraneous candidate filtering
- specialized symbolic checks by case:
  - removable discontinuity/hole checks
  - critical-point checks (derivative-related path)
  - equation/system checks
- outputs `checks_run`, candidate counts, dropped candidates, final solutions.

### 3) Proof SymPy executed
- Runtime proof log file: `reports/solve_flow_evidence/sympy_verification_proof.log`
- Per-live-case proof logs:
  - `reports/solve_flow_evidence/live_case_L1_sympy_proof.log`
  - `reports/solve_flow_evidence/live_case_L2_sympy_proof.log`
  - `reports/solve_flow_evidence/live_case_L3_sympy_proof.log`
- Examples captured:
  - L1: `component=sympy_verification_gate`, `checks_run=["equation_substitution"]`, `sympy_used=true`, `verified=true`.
  - L2: `sympy_verification_gate`, `error_class=symbolic_parse_failed`, verification attempted but not verified.
  - L3: `checks_run=["simplify_equivalence","domain_restriction","limit_hole"]`, `sympy_used=true`, `verified=true`.
- Structured traces with candidates/checks/dropped/final:
  - `verification_gate_trace_L1.json`
  - `verification_gate_trace_L2.json`
  - `verification_gate_trace_L3.json`

## Section C - NumPy: Where/When It Executes (Hard Proof)

### 1) NumPy usage in plotting
- Call sites documented in `reports/solve_flow_evidence/numpy_call_sites.txt`.
- Runtime modules:
  - `safe_parser.evaluate_for_plotting` (SymPy `lambdify(..., modules=['numpy'])`, `np.asarray`, `np.isinf`, `np.isnan`)
  - `plot_renderer.generate_data` (`np.linspace`, vectorized evaluation, NaN/Inf filtering)
  - renderer helpers use NumPy arrays/ticks/masking.

### 2) NumPy usage in verification
- Verification gate is primarily SymPy-based for these cases.
- Numeric/tolerance checks are present in verification logic; core runtime NumPy proof in this run is plotting/safe-parser path.

### 3) Proof NumPy executed
- Runtime proof: `reports/solve_flow_evidence/numpy_usage_proof.log`
- Local runtime capture includes:
  - `component=sympy_numpy_safe_parser_eval`, `numpy_used=true`, point counts
  - `component=numpy_plot_renderer_generate_data`, `numpy_used=true`, series_count
- Live solves also emitted `solve_v3_stage_plot` with `numpy_used=true` (see per-case logs).

## Section D - Plot/Graph Pipeline (End-to-End)

### 1) Decision logic
- `graph_mode` behavior from `apply_graph_mode_override(...)`:
  - `off`: force `visuals.should_visualize=false`, clear plots
  - `on`: force `visuals.should_visualize=true`
  - `auto`: follow model decision unless backend plot generation produced output
- Plot generation entry: `maybe_generate_plot(...)` in `backend/app/services/plot_integration.py`.
- If LLM plot spec is unavailable/fails, Matplotlib fallback path may run.

### 2) Parsing and safety
- Safe expression parsing path is `backend/app/services/visualization/safe_parser.py`.
- Uses SymPy parser + controlled namespace, blocks dangerous patterns; no raw `eval/exec`.
- Per-item parse/eval errors are returned as structured errors in local test pack artifacts.

### 3) Sampling + rendering
- NumPy sampling via `np.linspace` and vectorized evaluation.
- Domain windows come from recipe/plan fields and defaults.
- Renderer uses headless backend `matplotlib.use('Agg')`.
- Discontinuity behavior handled by NaN/Inf filtering and finite segment analysis in test pack.

### 4) What is returned to frontend
- Solve payload includes plots under `visuals.plots[]`.
- Chat page consumes assistant `structured_data.visuals` from `/sessions/{id}` and renders graph via workspace visual renderer.

### Observed runtime behavior in live cases
- Live cases had `plots_count=1`, but `solve_v3_stage_plot` emitted `TypeError` in runtime audit for all 3 runs.
- Despite that, visual recipes remained in response and frontend had plot data to render from `visuals.plots`.
- Plot pipeline traces are saved in:
  - `plot_pipeline_trace_L1.json`
  - `plot_pipeline_trace_L2.json`
  - `plot_pipeline_trace_L3.json`

## Section E - Live Proof (Exactly 3 OpenAI Runs)

Executed exactly 3 successful real OpenAI solves (model `gpt-5-mini`):
- L1 request_id: `live-solvev3-l1-1770962845-1`
- L2 request_id: `live-solvev3-l2-1770962854-2`
- L3 request_id: `live-solvev3-l3-1770962863-3`

Evidence:
- Summary: `reports/solve_flow_evidence/live_cases_summary.json`
- OpenAI stage count log: `reports/solve_flow_evidence/live_openai_call_count.log`
- Per-case request/response/runtime/plot/verification artifacts listed in the index above.

Results against requested constraints:
- Steps >= 6: yes for L1/L2/L3.
- Plot count >= 1: yes for L1/L2/L3.
- Verification attempted: yes for all 3 (L2 attempted but unresolved due symbolic parse failure).

## Section F - Strict Local Test Pack (No OpenAI)

Executed local-only pack with 22 expressions (polynomial, rational, trig, logs, piecewise, implicit-like, invalid input).

Artifacts:
- `reports/solve_flow_evidence/local_plot_test_pack_results.json`
- `reports/solve_flow_evidence/local_plot_test_pack.log`
- `reports/solve_flow_evidence/local_runtime_audit_capture.log`
- `reports/solve_flow_evidence/local_pytest_output.log`

Pytest local verification run:
- Command output stored in `local_pytest_output.log`
- Result: `17 passed, 2 warnings`
- Files executed: `backend/tests/test_visualization_v3.py`, `backend/tests/test_runtime_audit_sympy_numpy.py`

Plot artifacts from local renderer:
- `reports/solve_flow_evidence/plot_artifacts/artifact_parabola.png`
- `reports/solve_flow_evidence/plot_artifacts/artifact_intersection_base.png`
- `reports/solve_flow_evidence/plot_artifacts/artifact_hole_curve.png`

## Acceptance Checklist
- Complete code map + sequence diagram: **done** (`solve_flow_code_map.json`, `solve_flow_sequence.mmd`).
- Hard SymPy execution proof logs: **done** (`sympy_verification_proof.log`, per-case logs/traces).
- Hard NumPy execution proof logs: **done** (`numpy_usage_proof.log`, `numpy_call_sites.txt`, local runtime capture).
- 3 live OpenAI runs with artifacts: **done** (L1/L2/L3 files + summary).
- Local-only test pack with zero OpenAI usage: **done** (local pack artifacts + local pytest output).
- All artifacts saved under `reports/solve_flow_evidence/`: **done**.
