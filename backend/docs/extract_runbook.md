# Extract Questions Runbook

## Monitoring
- The extractor logs appear in the FastAPI terminal (run `uvicorn app.main:app --reload --port 8000` from the `backend/` directory).
- Look for lines that start with `extract_questions response raw content: …` (INFO level) and `Invalid JSON response from Extract engine` (ERROR).
- If text extraction fails, the log also prints `OpenAI extract response missing text` plus a truncated sanitized representation of the OpenAI payload.

## OCR Engines
- Supported engines: `pix2text` (local), `qwen_math` (Ollama), `openai` (`gpt-5-mini` via `VLM_MODEL_OPENA_AI_OCR`).
- AUTO routing order is deterministic: `pix2txt -> qwen -> openai`.
- OpenAI OCR uses prompt ID `openai_ocr_system_prompt_v1` and schema ID `youask_math_solver_openai_ocr_v1` from prompt registry tables.
- If `OPENAI_API_KEY` is missing, OpenAI is disabled from AUTO plans.

## Diagnostic Path
1. Upload/crop an image in Snap & Solve and hit **Send to AI**.
2. Watch for the INFO log above—if it prints `""` or `ResponseReasoningItem`, the model ignored the schema.
3. When `_parse_json_response` raises `ValueError`, the log includes a truncated snippet; copy that snippet to understand what the model returned.
4. Use the `EXTRACT_MODEL`, `EXTRACT_SYSTEM_PROMPT`, and `EXTRACT_USER_PROMPT` env vars (see `backend/app/api.py`) to tweak the instructions if the response still deviates.

## Troubleshooting
- If parsing fails repeatedly, check whether `text.format`/`response_format` payload is actually being sent (look for `text.format` in the request log).
- For partial JSON responses wrapped in fences, `_parse_json_response` strips fences and retries automatically before raising errors.
- When schema validation trips, the pipeline returns a safe fallback with `is_math_page: false` and logs the validation error details (`Extract schema validation failed`).

## Tips
- Use `EXTRACT_MAX_TOKENS`, `EXTRACT_MAX_MB`, and `EXTRACT_MODEL` to control request size without touching the core logic.
- Review `backend/tests/test_extract_parser.py` for representative parsing scenarios.
