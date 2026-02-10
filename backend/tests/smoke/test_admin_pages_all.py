import json
from pathlib import Path


def _manifest_path() -> Path:
    for parent in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        candidate = parent / "admin_nav_manifest.json"
        if candidate.exists():
            return candidate
    candidate = Path("/src/admin_nav_manifest.json")
    if candidate.exists():
        return candidate
    raise AssertionError("admin_nav_manifest.json not found in repo root or /src mount.")


def test_admin_ui_routes_exist():
    manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
    nav_items = manifest.get("nav_items", [])
    assert nav_items, "Manifest nav_items must not be empty"

    root = _manifest_path().parent
    missing = []
    for item in nav_items:
        if item.get("type") != "link":
            continue
        href = item.get("href")
        if not href:
            continue
        page = root / "src" / "app" / Path(href.lstrip("/")) / "page.tsx"
        if not page.exists():
            missing.append(f"{href} -> {page}")

    assert not missing, f"Missing admin pages: {missing}"
