# MathJax v4 TeX->SVG Stress Test Report

## Scope
- Endpoint tested: `POST http://localhost:9000/api/v1/math/render`
- Mode: local-only, backend-only render path
- OpenAI: disabled for test context (`DISABLE_OPENAI=true` guard in backend startup/tests)

## MathJax Version Detection
- Node: `v22.15.1`
- Worker package (`backend/tools/mathjax_renderer_v4`):
  - `@mathjax/src@4.1.0`
- Legacy package still exists elsewhere in repo (`mathjax-full@3.x`) but not used by `/api/v1/math/render` worker path.

Reference outputs:
- `docs/MathRender-Versions.md`
- `backend/tools/mathjax_renderer_v4/package.json`

## TeX Packages Enabled in Worker
From `backend/tools/mathjax_renderer_v4/renderer.mjs`:
- `base`
- `ams`
- `newcommand`
- `noundefined`

Autoload/require are not enabled.

## Stress Pack Inputs
- 10 complex display-mode formulas submitted in one batch (exact set from request).
- Options used:
```json
{
  "font": "tex",
  "sanitize": true,
  "return_metrics": true
}
```

## Run Results
### Run 1
- File: `reports/mathjax_svg_pack_run1.json`
- HTTP: `200`
- `results.length`: `10`
- `ok=true`: `10/10`
- Sanitizer checks (script/on*/foreignObject/javascript href): `clean for all 10`
- Stats:
  - `requested=10`
  - `deduped=10`
  - `cache_hits=0`
  - `rendered=10`
  - `latency_ms=177`
  - `roundtrip_ms=203.08`

### Run 2 (same payload)
- File: `reports/mathjax_svg_pack_run2.json`
- HTTP: `200`
- `results.length`: `10`
- `ok=true`: `10/10`
- Stats:
  - `requested=10`
  - `deduped=10`
  - `cache_hits=10`
  - `rendered=0`
  - `latency_ms=0`
  - `roundtrip_ms=9.01`

Cache behavior validated: second run served from cache with high hit rate.

## SVG Samples
Saved first-run outputs:
- `reports/svg_samples/mx-01.svg`
- `reports/svg_samples/mx-02.svg`
- `reports/svg_samples/mx-03.svg`
- `reports/svg_samples/mx-04.svg`
- `reports/svg_samples/mx-05.svg`
- `reports/svg_samples/mx-06.svg`
- `reports/svg_samples/mx-07.svg`
- `reports/svg_samples/mx-08.svg`
- `reports/svg_samples/mx-09.svg`
- `reports/svg_samples/mx-10.svg`

Sanitizer verification file:
- `reports/mathjax_svg_pack_checks.json`

## Chat/Edit + Export Fixes Applied
- File updated: `src/components/math-canvas/export/exportDocument.ts`
- Changes:
  - Added robust PDF fallback path (`window.open` popup -> hidden iframe) when `fetch` is unavailable or PDF endpoint fails.
  - Replaced hard `alert(...)` calls with guarded notifier to avoid runtime/test crashes.
  - Added explicit DOCX error handling for environments without `fetch`.
- This stabilizes export behavior used by:
  - Chat page canvas export flow
  - Edit page export buttons (PDF/DOCX)

## Validation for Chat/Edit Export Path
- Lint:
  - `npm run lint` -> pass (0 errors)
- Export unit tests:
  - `npx jest src/components/math-canvas/__tests__/exportDocument.test.ts --runInBand -u` -> pass (5/5)

## No OpenAI Calls Were Made
Proof points:
- Render tests hit only `/api/v1/math/render`.
- Backend guard path exists and was used in test context:
  - `DISABLE_OPENAI=true`
  - OpenAI manager init is skipped in `backend/app/main.py` when this flag is set.
- Integration test coverage includes explicit guard assertion:
  - `backend/tests/test_math_render_integration.py` (`test_disable_openai_guard_during_math_render`).
