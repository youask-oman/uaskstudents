# Math Render Version Detection

Date: 2026-02-12

## Detected Packages

- `@mathjax/src`: `4.1.0`
- `mathjax-full`: `3.2.2` (legacy v3 package)
- `mathjax` (unscoped): not installed as a top-level package

Detection evidence:

- `npm ls mathjax mathjax-full @mathjax/src` reports:
  - `better-react-mathjax -> @mathjax/src@4.1.0`
  - `better-react-mathjax -> mathjax-full@3.2.2`
- `package-lock.json` contains entries for both `@mathjax/src` and `mathjax-full`.
- Backend WhatsApp renderer code references `mathjax-full` paths.

## Directory/Bundle Structure

- v4 package structure detected under `node_modules/@mathjax/src/...`
  - Includes `bundle/` with v4 bundles (e.g. `tex-svg.js`, `node-main.mjs`).
- v3 legacy structure detected via `mathjax-full/js/...` imports in backend WhatsApp integration.

## Implementation Decision

- New backend LaTeX->SVG renderer is implemented against MathJax v4 (`@mathjax/src`) only.
- No OpenAI dependency is used for render paths.
- Legacy `mathjax-full` usage in WhatsApp remains separate and is not used by the new `/api/v1/math/render` pipeline.
