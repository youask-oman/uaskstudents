import json
from app.main import app
from fastapi.routing import APIRoute

def discover_routes():
    inventory = {
        "backend_endpoints": [],
        "ui_pages": []
    }
    
    # 1. Discover Backend Endpoints
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            # Check if it's an admin endpoint
            is_admin = False
            if path.startswith("/admin") or "/admin/" in path or "/api/v1/admin" in path:
                is_admin = True
            
            # Add to inventory if admin or explicitly requested non-admin critical endpoints
            if is_admin or any(p in path for p in ["/api/v1/users", "/api/v1/attempt", "/api/v1/invoices", "/api/v1/plans"]):
                inventory["backend_endpoints"].append({
                    "path": path,
                    "methods": list(route.methods),
                    "name": route.name,
                    "tags": list(route.tags)
                })

    # 2. Discover UI Pages (Static Discovery from layout.tsx)
    # Since I already read layout.tsx, I will hardcode the discovery logic here or just the data for now
    # But to be "automatic", I'll try to parse the layout.tsx if possible, or just use the known list.
    # The user said "MUST NOT hardcode page lists unless discovery fails".
    
    # Let's try to extract from layout.tsx using a simple regex or string search
    layout_path = "src/app/admin/layout.tsx"
    try:
        with open(layout_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Look for navItems array
            # Rough extraction: find strings starting with /admin
            import re
            links = re.findall(r'href:\s*"(/admin[^"]*|/adminpayments[^"]*)"', content)
            inventory["ui_pages"] = sorted(list(set(links)))
    except Exception as e:
        print(f"Failed to discover UI pages from layout: {e}")

    # Save to report
    with open("reports/admin_route_inventory.json", "w") as f:
        json.dump(inventory, f, indent=2)
    
    print(f"Discovered {len(inventory['backend_endpoints'])} backend endpoints")
    print(f"Discovered {len(inventory['ui_pages'])} UI pages")

if __name__ == "__main__":
    discover_routes()
