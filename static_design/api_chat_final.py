from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.utils.chat_final_payload import build_chat_final_payload

router = APIRouter()

@router.get("/api/chat_final/from_extracted")
def chat_final_from_extracted(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="file_not_found")

    data = json.loads(p.read_text(encoding="utf-8"))
    payload = build_chat_final_payload(data)
    return payload
