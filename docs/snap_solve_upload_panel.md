# Snap & Solve Upload/Sketch Panel (v2)

This feature is isolated to the Snap & Solve tab and does not modify Text/Voice behavior.

## Enable

Set:

```
NEXT_PUBLIC_SNAP_SOLVE_UPLOAD_PANEL_V2=true
```

## Backend Endpoint

`POST /api/v1/math/solve_from_image_or_sketch` (multipart/form-data)

Fields:
- `mode`: `upload` or `sketch`
- `question_text`: optional string
- `image`: optional file (upload image or sketch PNG)

## Local Verify

1. Open `/solve`
2. Click **Snap & Solve**
3. Upload flow:
   - drag/drop image
   - click upload
   - paste screenshot (Ctrl+V on Windows, Cmd+V on macOS)
4. Sketch flow:
   - switch to **Sketch**
   - draw/erase
   - submit

## Notes

- Paste listener is attached only while Snap panel is mounted.
- Sketch canvas is lazy-loaded (Fabric imported on demand).
- Max upload size defaults to 10MB.
