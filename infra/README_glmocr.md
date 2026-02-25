# GLM-OCR Direct Integration (No `glmocr-api` Service)

## Architecture

- No `glmocr-api` container/service.
- Backend endpoint `POST /api/extract/math-question` calls Ollama directly via `/api/generate`.
- Ollama runs on host OS (outside Docker).

## Host setup

1. Install Ollama on host.
2. Pull model:

```bash
ollama pull glm-ocr
```

3. Verify host API:

```bash
ollama list
curl http://localhost:11434/api/tags
```

## `OLLAMA_BASE_URL` configuration

- Backend on host: `OLLAMA_BASE_URL=http://localhost:11434`
- Backend in Docker (Windows/Mac): `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- Backend in Docker (Linux):
  - add `extra_hosts: ["host.docker.internal:host-gateway"]`, or
  - set `OLLAMA_BASE_URL` to host LAN IP, e.g. `http://192.168.x.x:11434`

Current compose already includes `extra_hosts` for Linux host-gateway mapping.

## Dataset harness

```bash
python scripts/test_glmocr_dataset.py --input ./mathquestions --out ./artifacts/glmocr_runs
```

For your local dataset path:

```bash
python scripts/test_glmocr_dataset.py --input ./static_design/mathquestions --out ./artifacts/glmocr_runs
```

Outputs:

- `artifacts/glmocr_runs/<timestamp>/<file_stem>/extraction.json`
- `artifacts/glmocr_runs/<timestamp>/<file_stem>/extraction.md`
- `artifacts/glmocr_runs/<timestamp>/summary.csv`
- `artifacts/glmocr_runs/<timestamp>/summary.json`
