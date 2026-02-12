# Runtime Audit: SymPy + NumPy

## 1) Environment
- OS: `Windows-10-10.0.26200-SP0`
- Python: `3.11.6`
- Docker runtime used: `uask-orchestrator:prod` (`localhost:9000 -> container:8000`)
- Package versions:
  - `sympy 1.14.0`
  - `numpy 2.2.6`
  - `matplotlib 3.10.8`
- Git commit: `7651b9290954a4e39b9e78d3a850efcf09d43180`
- Relevant env flags (`.env`):
  - `CANONICAL_CACHE_ENABLED=true` (`.env:24`)
  - `FEATURE_LOCAL_FIND_ERROR=true` (`.env:37`)
  - `RUNTIME_AUDIT_LOGGING` is not set in `.env`; enabled during tests via `monkeypatch.setenv`.
  - No additional plot-specific env flags were present in `.env` during this audit.

## 2) Where SymPy Is Used (Runtime-Proven)

### A) Canonicalization service
- Call path:
  - `backend/app/api.py:5062` -> `canonicalization_service.normalize_math_object(...)`
  - Function: `backend/app/services/solve/canonicalization_service.py:42`
- Repro input:
  - `sqrt(x+5) = x - 1`
  - `x^2 - 4` vs `(x-2)(x+2)`
  - `sin(x)^2 + cos(x)^2`
- Observed output:
  - Evidence: `reports/evidence/canonicalization_samples.json`
  - `x^2 - 4` and `(x-2)(x+2)` canonicalized to same key payload (`matched: true`).
- Proof artifact:
  - Runtime audit logs (`sympy_used=true`) in `reports/evidence/pytest_runtime_audit.log:58`

### B) Solution-doc parse + verification
- Call path:
  - `backend/app/services/solve/solution_doc.py:757` (`parse_solution_doc`)
  - `backend/app/services/solve/solution_doc.py:983` (`_verify_candidate`)
  - `backend/app/services/solve/solution_doc.py:1041` (`apply_algebra_autocorrect`)
  - Endpoint usage from `backend/app/api.py:8011`, `backend/app/api.py:8015`, `backend/app/api.py:8044`, `backend/app/api.py:8360`
- Repro input:
  - `sqrt(x) = x - 2` (extraneous root handling)
  - `(x+1)/(x-2)=3` (domain restriction `x != 2`)
  - `log(x) = 0` (real domain `x > 0`)
- Observed output:
  - Evidence: `reports/evidence/solution_doc_extraneous.json`
  - Autocorrect retained valid solution and dropped invalid candidates.
- Proof artifact:
  - Logs show parse + candidate verification + autocorrect:
    - `sympy_solution_doc_parse` `reports/evidence/pytest_runtime_audit.log:65`
    - `sympy_solution_doc_verify_candidate` `reports/evidence/pytest_runtime_audit.log:66`
    - `sympy_solution_doc_autocorrect` `reports/evidence/pytest_runtime_audit.log:67`

### C) Safe plot parsing (no eval)
- Call path:
  - `backend/app/services/visualization/safe_parser.py:105` (`parse_expression`)
  - `backend/app/services/visualization/safe_parser.py:205` (`evaluate_for_plotting`)
  - Used by renderer through `backend/app/services/visualization/plot_renderer.py:300`
- Repro input:
  - Valid: `sin(x)/x`, `x**2 + 3*x - 1`
  - Malicious: `__import__("os").system("echo hacked")`, `lambda x: x`
- Observed output:
  - Evidence: `reports/evidence/safe_parser_samples.json`
  - Valid expressions parsed/evaluated; malicious payloads rejected as unsafe.
- Proof artifact:
  - `sympy_safe_parser_parse` and `sympy_numpy_safe_parser_eval` logs:
    - `reports/evidence/pytest_runtime_audit.log:78`
    - `reports/evidence/pytest_runtime_audit.log:81`

### D) Error localizer
- Call path:
  - Endpoint: `backend/app/bg_routers/local_router.py:384`
  - Endpoint function: `backend/app/bg_routers/local_router.py:385`
  - SymPy localizer entry: `backend/app/services/math/error_localizer.py:507`
- Repro input:
  - OCR text equivalent used in test endpoint flow: `2(x+1)=2x+1` (bad distribution)
- Observed output:
  - Response includes detected wrong line and reason.
  - Evidence: `reports/evidence/api_find_error_local.json`
- Proof artifact:
  - Runtime audit log: `sympy_error_localizer_entry` at `reports/evidence/pytest_runtime_audit.log:92`

### E) Step generator (conditional, low confidence)
- Call path:
  - `backend/app/bg_routers/local_router.py:463` calls `generate_local_steps(norm_text)`
  - Entry: `backend/app/services/math/step_generator.py:7`
- Forced low-confidence mechanism:
  - In test, `find_first_error_from_ocr` is mocked to return `confidence=0.2` and no definite wrong line.
  - This forces the conditional branch to invoke step generation.
- Observed output:
  - Response contains `local_steps: ["forced low confidence steps"]`
  - Evidence: `reports/evidence/api_find_error_local_low_confidence.json`
- Proof artifact:
  - Runtime audit log: `sympy_step_generator_entry` at `reports/evidence/pytest_runtime_audit.log:93`

## 3) Where NumPy Is Used (Mapped + Proven)

### A) All `import numpy` runtime locations
- `backend/app/services/plot_pipeline_service.py:15`
- `backend/app/services/math/error_localizer.py:12`
- `backend/app/services/ocr/ocr_service.py:69`
- `backend/app/services/visualization/plot_renderer.py:14`
- `backend/app/services/visualization/safe_parser.py:15`

Evidence map files:
- `reports/evidence/numpy_imports.txt`
- `reports/evidence/numpy_usages.txt`

### B) NumPy usage categories
- Plotting data prep/render:
  - `plot_renderer.py` (`np.linspace`, `np.isnan`, `np.isinf`, random generation, etc.)
  - `plot_pipeline_service.py` (`np.linspace`, `np.isfinite`, trig/log helpers)
- Expression evaluation arrays:
  - `safe_parser.py` (`np.asarray`, `np.isinf`, `np.isnan`)
- Error-localization numeric checks:
  - `error_localizer.py` (`np.random.default_rng`, `np.median`, `np.abs`)
- OCR/image array handling:
  - `ocr_service.py` (NumPy imported for OCR pipeline internals)

### C) Runtime NumPy proofs (2+)
- Proof 1 (unit/runtime): safe parser evaluation with NumPy array input/output.
  - Test: `tests/test_runtime_audit_sympy_numpy.py`
  - Log: `sympy_numpy_safe_parser_eval` with `numpy_used=true`
  - Artifact: `reports/evidence/pytest_runtime_audit.log:81`
  - Output artifact: `reports/evidence/safe_parser_samples.json`
- Proof 2 (endpoint/runtime): error localizer endpoint path executed with NumPy-enabled localizer flow.
  - Test endpoint: `/api/v1/find_error_local` via `TestClient`
  - Log: `sympy_error_localizer_entry` with `numpy_used=true`
  - Artifact: `reports/evidence/pytest_runtime_audit.log:92`
  - Response artifact: `reports/evidence/api_find_error_local.json`

## 4) Evidence Appendix

### Commands run
- Versions:
  - `python -c "import platform,sys; print(platform.platform()); print(sys.version)"`
  - `pip show sympy numpy matplotlib`
  - `python -c "import sympy,numpy,matplotlib; print('sympy',sympy.__version__); print('numpy',numpy.__version__); print('matplotlib',matplotlib.__version__)"`
- Git:
  - `git rev-parse HEAD`
- Env flags:
  - `rg -n "CANONICAL_CACHE_ENABLED|FEATURE_LOCAL_FIND_ERROR|RUNTIME_AUDIT_LOGGING|PLOT|GRAPH_MODE|LOCAL_FINDERR" .env -S`
- NumPy audit:
  - `rg -n "import numpy as np|import numpy" backend/app -S`
  - `rg -n "\bnp\." backend/app -S`
- Tests:
  - `pytest -q tests/test_runtime_audit_sympy_numpy.py`
  - `pytest -q tests/test_runtime_audit_sympy_numpy.py -o log_cli=true -o log_cli_level=DEBUG > reports/evidence/pytest_runtime_audit.log`
- Live API cURL (Docker backend on `localhost:9000`):
  - `curl -s "http://localhost:9000/api/v1/solve_v3_runtime_meta?user_id=1&tier=standard&mode_family=SOLVE&requested_mode=minimal"`
  - `curl -s -X POST "http://localhost:9000/api/v1/find_error_local?user_id=1" -F "file=@reports/evidence/blank.png;type=image/png" -F "selection_bbox_json={\"x\":0.1,\"y\":0.1,\"w\":0.8,\"h\":0.8}" -F "max_lines=6"`
  - `curl -s -X POST "http://localhost:9000/api/v1/plot/pipeline" -H "Content-Type: application/json" --data "{\"problem_text\":\"plot y=x^2\",\"solve_result\":{\"visuals\":{\"should_visualize\":true,\"plots\":[]}},\"graph_mode\":\"on\",\"tier\":\"STANDARD\",\"question_id\":\"audit\",\"use_reliable_pipeline\":false}"`

### Key log excerpts
- Runtime audit lines are captured in:
  - `reports/evidence/pytest_runtime_audit.log`
- High-signal lines:
  - `sympy_canonicalization`: `reports/evidence/pytest_runtime_audit.log:58`
  - `sympy_solution_doc_parse`: `reports/evidence/pytest_runtime_audit.log:65`
  - `sympy_solution_doc_verify_candidate`: `reports/evidence/pytest_runtime_audit.log:66`
  - `sympy_safe_parser_parse`: `reports/evidence/pytest_runtime_audit.log:78`
  - `sympy_numpy_safe_parser_eval`: `reports/evidence/pytest_runtime_audit.log:81`
  - `sympy_error_localizer_entry`: `reports/evidence/pytest_runtime_audit.log:92`
  - `sympy_step_generator_entry`: `reports/evidence/pytest_runtime_audit.log:93`

### API/JSON artifacts
- `reports/evidence/canonicalization_samples.json`
- `reports/evidence/solution_doc_extraneous.json`
- `reports/evidence/safe_parser_samples.json`
- `reports/evidence/api_find_error_local.json`
- `reports/evidence/api_find_error_local_low_confidence.json`
- `reports/evidence/api_solve_v3_runtime_meta.json`
- `reports/evidence/curl_solve_v3_runtime_meta.json`
- `reports/evidence/curl_find_error_local.json`
- `reports/evidence/curl_plot_pipeline.json`

## Notes
- Route contracts were not changed.
- Instrumentation is guarded by `RUNTIME_AUDIT_LOGGING=true`.
- Existing behavior differences observed:
  - `sin(x)^2 + cos(x)^2` canonical solve-form simplifies to boolean false-equation form (`false`) under current canonicalization logic.
  - Some live cURL responses returned `404`/`500` due runtime data/state constraints (e.g., missing user or local OCR path), while deterministic endpoint execution evidence is provided via integration tests and captured logs.
