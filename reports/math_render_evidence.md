# Math Render Evidence

## Version Detection
- Node: `v22.15.1`
- MathJax worker package: `@mathjax/src@4.1.0`
- Legacy package still present elsewhere: `mathjax-full@3.2.2` (not used by `/api/v1/math/render` path)
- Full detection note: `docs/MathRender-Versions.md`

## Implemented Runtime Path
- Backend-only endpoint: `POST /api/v1/math/render`
- SVG retrieval endpoint: `GET /api/v1/math/svg/{key}.svg`
- Worker: `backend/tools/mathjax_renderer_v4/renderer.mjs`
- Sanitizer: `backend/tools/mathjax_renderer_v4/sanitize_svg.js` + server-side guard in `backend/app/services/math_render_service.py`
- Cache table migration: `backend/alembic/versions/20260212_math_svg_cache.py`

## No OpenAI Proof
- Test guard enforces no OpenAI manager initialization during math-render tests:
  - `backend/tests/test_math_render_integration.py:55`
- Guard variable used for local runs:
  - `DISABLE_OPENAI=true`
- App startup skip path for OpenAI manager in this mode:
  - `backend/app/main.py` (DISABLE_OPENAI branch)

## Test Results
- Command:
  - `pytest -q backend/tests/test_math_render_unit.py backend/tests/test_math_render_integration.py`
- Result:
  - `6 passed`

## Render Test Pack (100+ formulas)
- Command:
  - `DISABLE_OPENAI=true python backend/scripts/render_test_pack.py`
- Summary (`backend/reports/evidence/math_render/render_pack_summary.json`):
  - requested: `123`
  - first run: `ok=111`, `error=12`, `http_status=200`
  - second run: `http_status=200`, cache hits present, no request failure
  - latency: `p50=4ms`, `p95=9ms`

## Evidence Artifacts
- `backend/reports/evidence/math_render/render_pack_request.json`
- `backend/reports/evidence/math_render/render_pack_first.json`
- `backend/reports/evidence/math_render/render_pack_second.json`
- `backend/reports/evidence/math_render/render_pack_summary.json`
- `backend/reports/evidence/math_render/sample_svg_snippets.txt`

## Frontend Display Mode Update
- Removed global client MathJax context from app layout.
- `src/components/math/UnifiedMathRenderer.tsx` now batches formulas to backend `/api/v1/math/render` and displays backend SVGs.
- Streaming mode (`dynamic=true`) now renders raw text only (no math parsing/typesetting during stream).

## Lint Status
- Command: `npm run lint`
- Result: `0 errors`, `1 warning` (`@next/next/no-img-element` in `src/components/math/UnifiedMathRenderer.tsx`).
