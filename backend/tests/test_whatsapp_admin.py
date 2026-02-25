from pathlib import Path


def test_legacy_v1_admin_whatsapp_routes_are_guarded():
    src = Path("backend/app/api.py").read_text(encoding="utf-8")
    assert '@api_router.get("/admin/whatsapp/status")' in src
    assert '@api_router.post("/admin/whatsapp/initialize")' in src
    assert '@api_router.post("/admin/whatsapp/disconnect")' in src
    assert "Depends(get_admin_user)" in src


def test_admin_router_whatsapp_routes_use_admin_dependency():
    src = Path("backend/app/api_admin.py").read_text(encoding="utf-8")
    assert '@admin_router.get("/whatsapp/status")' in src
    assert '@admin_router.post("/whatsapp/initialize")' in src
    assert '@admin_router.post("/whatsapp/disconnect")' in src
    assert '@admin_router.get("/whatsapp/monitor")' in src
    # Each endpoint should be protected by backend-admin dependency.
    assert "admin: User = Depends(get_admin_user)" in src
