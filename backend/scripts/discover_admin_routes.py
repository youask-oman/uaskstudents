import sys
import json
import os
import re
from pathlib import Path

# Add backend directory to path to import app modules
# Path(__file__) is backend/scripts/discover_admin_routes.py
# parents[0] is backend/scripts
# parents[1] is backend
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.main import app
from fastapi.routing import APIRoute

ROOT = Path(__file__).resolve().parents[2]

def discover_routes():
    inventory = {
        "backend_endpoints": [],
        "ui_pages": []
    }
    
    # 1. Discover Backend Endpoints
    # (Existing logic same as before, but ensure prefixes are comprehensive)
    admin_prefixes = [
        "/admin", "/api/admin", "/api/v1/admin",
        "/api/v1/billing/admin", "/api/v1/refunds", "/api/v1/ledger",
        "/api/v1/hold", "/api/v1/audit", "/api/v1/admin-health"
    ]
    critical_prefixes = [
        "/api/v1/users", "/api/v1/attempt", "/api/v1/invoices",
        "/api/v1/plans", "/api/v1/subscriptions"
    ]

    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            is_admin = any(path.startswith(p) for p in admin_prefixes)
            is_admin_tagged = any(tag in ["admin", "billing_admin", "staff"] for tag in (route.tags or []))
            
            if is_admin or is_admin_tagged or any(path.startswith(cp) for cp in critical_prefixes):
                inventory["backend_endpoints"].append({
                    "path": path,
                    "methods": list(route.methods),
                    "name": route.name,
                    "tags": list(route.tags or [])
                })

    # 2. Discover UI Pages
    # Try multiple possible locations for src
    base_src = None
    possible_src_paths = [
        Path("/src/src"),              # Container mount .:/src -> /src/src
        Path("/src"),                  # Alternative mount
        Path("/app/src"),              # Alternative container mount
        backend_dir.parent / "src",    # Host relative
    ]
    
    for p in possible_src_paths:
        if p.exists() and (p / "app" / "admin").exists():
            base_src = p
            break
            
    if base_src:
        print(f"Found UI source at: {base_src}")
        # Check layout.tsx
        # Next.js app router: src/app/admin/layout.tsx or app/admin/layout.tsx
        layout_path = base_src / "app" / "admin" / "layout.tsx"
        if not layout_path.exists():
            # Try without 'src' prefix if base_src already points to src
            layout_path = base_src / "admin" / "layout.tsx"
            
        if layout_path.exists():
            try:
                content = layout_path.read_text(encoding="utf-8")
                links = re.findall(r'href:\s*"(/admin[^"]*|/adminpayments[^"]*)"', content)
                inventory["ui_pages"].extend(links)
            except Exception as e:
                print(f"Failed to discover UI pages from layout: {e}")

        # Check filesystem
        admin_app_dir = base_src / "app" / "admin"
        for root, dirs, files in os.walk(admin_app_dir):
            if "page.tsx" in files:
                # Convert path to route
                # rel_path is from 'app' relative
                rel_path = Path(root).relative_to(base_src / "app")
                route_path = "/" + str(rel_path).replace("\\", "/")
                inventory["ui_pages"].append(route_path)
    else:
        print("Warning: UI source directory not found. UI page discovery skipped.")

    inventory["ui_pages"] = sorted(list(set(inventory["ui_pages"])))

    # Save to report - use absolute path inside backend
    report_path = backend_dir / "reports" / "admin_route_inventory.json"
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(inventory, f, indent=2)
    
    print(f"Discovered {len(inventory['backend_endpoints'])} backend endpoints")
    print(f"Discovered {len(inventory['ui_pages'])} UI pages")
    print(f"Inventory saved to {report_path}")

if __name__ == "__main__":
    discover_routes()
