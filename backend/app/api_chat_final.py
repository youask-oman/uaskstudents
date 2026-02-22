from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.utils.chat_final_payload import build_chat_final_payload

router = APIRouter()


@router.get("/api/chat_final/from_extracted")
def chat_final_from_extracted(path: str = Query(..., description="Absolute or workspace-relative extracted JSON path")):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="file_not_found")

    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="strict"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid_json: {exc}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid_payload_root")

    return build_chat_final_payload(data)
