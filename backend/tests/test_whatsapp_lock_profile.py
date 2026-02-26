from pathlib import Path


def test_profile_exposes_whatsapp_lock_fields():
    src = Path("backend/app/api.py").read_text(encoding="utf-8")
    assert "whatsapp_lock_active: bool = False" in src
    assert "whatsapp_lock_scope: Optional[str] = None" in src
    assert "whatsapp_lock_ttl_seconds: Optional[int] = None" in src
    assert "whatsapp_lock_reason: Optional[str] = None" in src
    assert "whatsapp_unlock_requested: bool = False" in src


def test_unlock_request_endpoint_exists():
    src = Path("backend/app/api.py").read_text(encoding="utf-8")
    assert '@api_router.post("/user/whatsapp/unlock-request")' in src
    assert "wa_abuse.submit_unlock_request(" in src
