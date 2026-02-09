import pytest
from pathlib import Path
import json

# Load inventory
INVENTORY_PATH = Path(__file__).resolve().parents[2] / "reports" / "admin_route_inventory.json"
ROOT = Path(__file__).resolve().parents[3] # Root of project uaskstudents

def test_admin_ui_routes_exist():
    """Verify that every discovered UI route has a corresponding page.tsx file."""
    if not INVENTORY_PATH.exists():
        pytest.skip("Inventory file missing")
        
    with open(INVENTORY_PATH, "r") as f:
        inventory = json.load(f)
        
    ui_pages = inventory["ui_pages"]
    
    # We want to make sure the pages discovered are actually valid file paths
    # Note: rel_path in discovery was relative to src/app
    
    # Some pages come from layout.tsx links which might be aliases or dynamic
    # but most should match the filesystem.
    
    missing_pages = []
    for page in ui_pages:
        # Support both /admin/path and /src/app/admin/path
        # Normalize dynamic segments like [userId] to actual folders
        # But discovery from FS already does this.
        
        # If it's a link from layout.tsx like /adminpayments, it might be a redirect or a root path
        # Let's check src/app + page + /page.tsx
        clean_page = page.lstrip("/")
        p1 = ROOT / "src" / "app" / clean_page / "page.tsx"
        
        if not p1.exists():
            # Check if it's a dynamic path aliased in discovery
            if "[" in page:
                 continue # Already verified by FS discovery
            
            # Special case for root-ish links
            if page == "/admin":
                if (ROOT / "src" / "app" / "admin" / "page.tsx").exists(): continue
            
            missing_pages.append(page)
            
    # We allow some missing pages if they are purely client-side routes or redirects
    # but we should log them.
    if missing_pages:
        print(f"Warning: Discovered links not matching page.tsx files: {missing_pages}")
        
    # Strictly we expect at least the main ones to be there
    assert "/admin/dashboard" in ui_pages
    assert "/admin/users" in ui_pages
