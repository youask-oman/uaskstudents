# SnapSolve v2: Single Page + Crop + GPT-5 Vision OCR

## Summary
Snap & Solve v2 supports one image or one PDF at a time, with single-page selection, crop, and OCR extraction using GPT-5 vision. The client renders PDF pages locally, exports cropped regions as compressed JPEG, and sends only the cropped bytes to the backend.

## Client Flow
1) Upload single image (JPG/PNG/WEBP) or PDF.
2) If PDF, select one page and render to canvas.
3) Crop or toggle full-page.
4) Send cropped image to `/api/v1/ocr_v5`.
5) Show extracted text and optional question list.
6) Select a question to solve immediately.

## Status States
- uploading
- rendering
- cropping
- reading
- done
- error

## Backend Endpoint
POST `/api/v1/ocr_v5` (multipart)
- file: image/jpeg or image/png or image/webp
- page_number: int
- file_hash: sha256 of original file (client computed)
- crop_x/crop_y/crop_w/crop_h: optional crop box in rendered pixel coords

Response JSON:
```
{
  "ok": true,
  "extracted_text": "...",
  "extracted_markdown": "...",
  "questions": ["..."],
  "cache_hit": false,
  "latency_ms": 1234,
  "input_tokens": 120,
  "output_tokens": 340,
  "cached_tokens": 0
}
```

## Caching
Cache key is sha256(image bytes + crop metadata). Results are stored in `OcrCache`.

## Limits
- Max upload size: `OCR_V5_MAX_MB` (default 10MB)
- Max output tokens: `OCR_V5_MAX_TOKENS` (default 800)
Here are exact commands to run the tests from the repo root.

Frontend (SnapSolveV2):

npx jest src/components/snap/__tests__/SnapSolveV2.test.tsx
Backend (OCR v5):

pytest backend/app/tests/test_ocr_v5.py
If you want to run both in one go:

npx jest src/components/snap/__tests__/SnapSolveV2.test.tsx && pytest backend/app/tests/test_ocr_v5.py