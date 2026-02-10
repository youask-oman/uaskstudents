import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import User
from scripts.seed_production import run_seed


def _manifest_path() -> Path:
    for parent in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        candidate = parent / "admin_nav_manifest.json"
        if candidate.exists():
            return candidate
    candidate = Path("/src/admin_nav_manifest.json")
    if candidate.exists():
        return candidate
    raise AssertionError("admin_nav_manifest.json not found in repo root or /src mount.")


def _load_manifest() -> dict:
    path = _manifest_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _auth_header(email: str, password: str) -> dict:
    client = TestClient(app)
    resp = client.post("/api/v1/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_superadmin_email() -> str:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.role == "superadmin")).first()
        assert user is not None, "No seeded superadmin user found."
        return user.email


def _page_file_for_href(href: str) -> Path:
    root = _manifest_path().parent
    clean = href.lstrip("/")
    return root / "src" / "app" / Path(clean) / "page.tsx"


def test_admin_nav_manifest_strict():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = "DevOnlyChangeMe123!"
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    manifest = _load_manifest()
    assert isinstance(manifest.get("version"), int), "Manifest must include integer version."
    nav_items = manifest.get("nav_items", [])
    assert isinstance(nav_items, list) and nav_items, "Manifest nav_items must be a non-empty list."

    hrefs = []
    labels = []
    api_checks = []
    for item in nav_items:
        assert item.get("type") in ("link", "divider"), f"Invalid nav item type: {item}"
        assert item.get("hidden") is not True, f"Hidden nav item detected: {item}"
        if item["type"] == "link":
            assert item.get("label"), f"Missing label for nav item: {item}"
            assert item.get("href"), f"Missing href for nav item: {item}"
            hrefs.append(item["href"])
            labels.append(item["label"])

            page_title = item.get("page_title")
            assert page_title, f"Missing page_title for {item['href']}"
            page_file = _page_file_for_href(item["href"])
            assert page_file.exists(), f"Missing page file for {item['href']}: {page_file}"
            content = page_file.read_text(encoding="utf-8")
            assert page_title in content, f"Page title '{page_title}' not found in {page_file}"

            for api_path in item.get("api_checks", []) or []:
                api_checks.append(api_path)

    assert len(hrefs) == len(set(hrefs)), "Duplicate hrefs detected in manifest."
    assert len(labels) == len(set(labels)), "Duplicate labels detected in manifest."

    if api_checks:
        superadmin_email = _get_superadmin_email()
        password = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
        headers = _auth_header(superadmin_email, password)
        client = TestClient(app)
        for path in api_checks:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text}"
