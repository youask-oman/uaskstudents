# SnapSolve v2: Extract + Solve Pipeline

## Summary
Snap & Solve v2 supports one image or one PDF at a time, renders one page on the client, and runs a two-step pipeline:
1) Extract questions from the selected region or whole page.
2) Solve selected questions with credit holds and per-question results.

## Client Flow
1) Upload single image (JPG/PNG/WEBP) or PDF.
2) If PDF, select one page and render to canvas.
3) Crop or toggle full-page.
4) Send cropped image to `/api/v1/extract_questions`.
5) Show question list (valid + invalid with reasons).
6) Optional: crop figure for questions that require a figure.
7) Solve selected via `/api/v1/solve_questions_batch`.

## Status States
- uploading
- rendering
- cropping
- extracting
- ready
- solving
- done
- error

## Backend Endpoints
### POST `/api/v1/extract_questions` (multipart)
Fields:
- file: image/jpeg or image/png or image/webp
- file_hash: sha256 of original file (client computed)
- page_number: int (optional)
- crop_x/crop_y/crop_w/crop_h: optional crop box in rendered pixel coords
- rotation: optional
- render_scale: optional
- source: "pdf_page" | "image"
- user_selection: "whole_page" | "crop"

Response JSON:
```
{
  "ok": true,
  "is_math_page": true,
  "notes": ["..."],
  "questions": [
    {
      "id": "q1",
      "text": "...",
      "confidence": 0.9,
      "is_valid_math": true,
      "reason_if_invalid": null,
      "type": "algebra",
      "bbox": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.2},
      "requires_figure": false
    }
  ],
  "cache_hit": false,
  "telemetry": {"request_id": "..."}
}
```

### POST `/api/v1/solve_questions_batch`
Body JSON:
```
{
  "items": [
    {
      "question_id": "q1",
      "text": "...",
      "requested_mode": "minimal",
      "requires_figure": false,
      "figure_image_base64": null
    }
  ],
  "features_used": {"ocr_used": true}
}
```

Response JSON:
```
{
  "ok": true,
  "results": [
    {
      "question_id": "q1",
      "ok": true,
      "solve_response_json": {"final_answer": {"answer_text": "..."}},
      "telemetry": {"input_tokens": 10, "output_tokens": 20},
      "credits_reserved": 1.2,
      "credits_final": 1.0,
      "credits_refunded": 0.2
    }
  ]
}
```

## Caching
Extraction cache key is sha256(image bytes + extract metadata). Results are stored in `OcrExtractionCache`.

## Limits
- Max upload size: `EXTRACT_MAX_MB` (default 10MB)
- Max output tokens: `EXTRACT_MAX_TOKENS` (default 900)

## Tests
Frontend:
- `npx jest src/components/snap/__tests__/SnapSolveV2.test.tsx`

Backend:
- `pytest backend/tests/test_snap_solve_pipeline.py`
