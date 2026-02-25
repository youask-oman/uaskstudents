import fs from "fs";
import path from "path";

const ROOT = process.cwd();
const ADMIN_DIR = path.join(ROOT, "src", "app", "admin");
const MANIFEST_PATH = path.join(ROOT, "admin_nav_manifest.json");
const OUT_JSON = path.join(ROOT, "docs", "admin_capability_matrix.json");
const OUT_MD = path.join(ROOT, "docs", "admin_capability_matrix.md");

const EXCLUDED_ROUTES = {
  "/admin/users/[id]": "Context detail route reachable from /admin/users",
  "/admin/billing/users/[userId]/wallet": "Context detail route reachable from billing inspector/ledger links",
  "/admin/billing/programs/enrollments": "Program-scoped enrollments detail route; primary entry is /admin/billing/enrollments",
  "/admin/billing/legacy": "Legacy compatibility page; intentionally not in primary nav",
  "/admin/legacy/payments": "Deprecated legacy route kept for backward compatibility",
  "/admin/legacy/plans": "Deprecated legacy route kept for backward compatibility",
  "/admin/legacy/subscriptions": "Deprecated legacy route kept for backward compatibility",
};

const ROLE_OVERRIDES = {
  "/admin/billing/topup-products": "superadmin (mutations), admin (read-only)",
  "/admin/billing/refunds": "admin+ (refund execution may require elevated role)",
};

function walkPages(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walkPages(p));
      continue;
    }
    if (entry.isFile() && entry.name === "page.tsx") {
      out.push(p);
    }
  }
  return out;
}

function toRoute(filePath) {
  const rel = path.relative(ADMIN_DIR, filePath).replace(/\\/g, "/");
  if (rel === "page.tsx") return "/admin";
  const route = "/admin/" + rel.replace(/\/page\.tsx$/, "");
  return route.replace(/\/+/g, "/");
}

function loadManifest() {
  const raw = fs.readFileSync(MANIFEST_PATH, "utf8");
  const parsed = JSON.parse(raw);
  const links = (parsed.nav_items || []).filter((x) => x?.type === "link" && typeof x?.href === "string");
  return links;
}

function buildMatrix() {
  const manifestLinks = loadManifest();
  const navLinks = manifestLinks.filter((x) => String(x.href).startsWith("/admin"));
  const navMap = new Map(navLinks.map((x) => [x.href, x]));

  const pageRoutes = walkPages(ADMIN_DIR).map(toRoute).sort();
  const rows = [];

  for (const route of pageRoutes) {
    const navItem = navMap.get(route);
    const excludedReason = EXCLUDED_ROUTES[route];
    const status = navItem ? "OK" : excludedReason ? "Intentionally Hidden" : "Missing in Nav";
    rows.push({
      capability: navItem?.label || route,
      ui_tab: navItem?.label || (excludedReason ? "(excluded)" : "(missing)"),
      route,
      backend_endpoints: Array.isArray(navItem?.api_checks) ? navItem.api_checks : [],
      permission_role: ROLE_OVERRIDES[route] || "admin",
      feature_flag: "none",
      status,
      notes: excludedReason || "",
    });
  }

  for (const navItem of navLinks) {
    if (!pageRoutes.includes(navItem.href)) {
      rows.push({
        capability: navItem.label || navItem.href,
        ui_tab: navItem.label || navItem.href,
        route: navItem.href,
        backend_endpoints: Array.isArray(navItem.api_checks) ? navItem.api_checks : [],
        permission_role: "admin",
        feature_flag: "none",
        status: "Route Missing",
        notes: "Nav entry points to a route without page.tsx",
      });
    }
  }

  rows.sort((a, b) => String(a.route).localeCompare(String(b.route)));
  return rows;
}

function writeOutputs(rows) {
  const payload = {
    generated_at: new Date().toISOString(),
    total: rows.length,
    rows,
  };
  fs.mkdirSync(path.dirname(OUT_JSON), { recursive: true });
  fs.writeFileSync(OUT_JSON, JSON.stringify(payload, null, 2), "utf8");

  const lines = [];
  lines.push("# Admin Capability Matrix");
  lines.push("");
  lines.push(`Generated: ${payload.generated_at}`);
  lines.push("");
  lines.push("| Capability | UI Tab | Route | Backend Endpoints | Permission/Role | Feature Flag | Status | Notes |");
  lines.push("|---|---|---|---|---|---|---|---|");
  for (const row of rows) {
    const endpoints = (row.backend_endpoints || []).join("<br/>");
    lines.push(
      `| ${row.capability} | ${row.ui_tab} | \`${row.route}\` | ${endpoints} | ${row.permission_role} | ${row.feature_flag} | ${row.status} | ${row.notes || ""} |`
    );
  }
  fs.writeFileSync(OUT_MD, lines.join("\n") + "\n", "utf8");
}

function main() {
  const checkOnly = process.argv.includes("--check");
  const rows = buildMatrix();
  if (!checkOnly) {
    writeOutputs(rows);
  } else {
    if (!fs.existsSync(OUT_JSON)) {
      console.error(`Missing capability matrix file: ${OUT_JSON}`);
      process.exit(1);
    }
    const existing = JSON.parse(fs.readFileSync(OUT_JSON, "utf8"));
    const existingRows = Array.isArray(existing?.rows) ? existing.rows : [];
    const a = JSON.stringify(existingRows.map((x) => ({ route: x.route, status: x.status, ui_tab: x.ui_tab })));
    const b = JSON.stringify(rows.map((x) => ({ route: x.route, status: x.status, ui_tab: x.ui_tab })));
    if (a !== b) {
      console.error("Capability matrix is out of date. Run: npm run admin:capabilities:generate");
      process.exit(1);
    }
  }

  const blocking = rows.filter((x) => x.status === "Missing in Nav" || x.status === "Route Missing");
  if (blocking.length > 0) {
    console.error("Admin capability audit failed:");
    for (const row of blocking) {
      console.error(`- ${row.status}: ${row.route}`);
    }
    process.exit(1);
  }
  console.log(`Admin capability audit passed. rows=${rows.length}`);
}

main();
