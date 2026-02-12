# MathJax v4 Backend Renderer

Backend-only LaTeX -> SVG worker using MathJax v4 components.

## Run locally

```bash
cd backend/tools/mathjax_renderer_v4
npm install
node renderer.mjs
```

Send JSONL records over stdin:

```json
{"id":"1","latex":"x\\neq 2","display_mode":true,"macros":{},"scale":1.0,"sanitize":true,"font":"tex"}
```

Output JSONL:

```json
{"id":"1","ok":true,"svg":"<svg...>...</svg>","metrics":{"width":5.4,"height":2.1,"baseline":null,"duration_ms":14}}
```

or

```json
{"id":"1","ok":false,"error":{"code":"TEX_PARSE_ERROR","message":"..."},"fallback_text":"x\\neq 2"}
```

