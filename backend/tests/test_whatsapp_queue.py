from pathlib import Path


def _extract_whatsapp_handler_block(source: str) -> str:
    start = source.index('@api_router.post("/whatsapp/message")')
    end = source.index('@api_router.post("/solve/clarify"')
    return source[start:end]


def test_whatsapp_message_handler_is_queue_only():
    src = Path("backend/app/api.py").read_text(encoding="utf-8")
    block = _extract_whatsapp_handler_block(src)
    assert "verify_request_signature(request)" in block
    assert "enforce_rate_limit(" in block
    assert "enforce_dedup(" in block
    assert "enforce_caps(" in block
    assert 'send_task(\n            "whatsapp_solve"' in block
    assert 'send_task(\n                "whatsapp_ocr_extract"' in block or '"whatsapp_ocr_extract"' in block
    assert "solver_service.solve_problem" not in block


def test_profile_response_no_secret_leakage_and_auth_guarded():
    src = Path("backend/app/api.py").read_text(encoding="utf-8")
    section_start = src.index("class UserProfileResponse(BaseModel):")
    section_end = src.index("@api_router.post(\"/signup\")")
    section = src[section_start:section_end]
    assert "whatsapp_secret" not in section
    assert "whatsapp_linked: bool = False" in src
    assert "current_user: User = Depends(get_current_user)" in src
