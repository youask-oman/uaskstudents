import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
const navManifest = JSON.parse(fs.readFileSync(path.resolve("admin_nav_manifest.json"), "utf-8"));

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "admin1234";
const EVIDENCE_DIR = path.resolve("reports/evidence");

fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

function writeJson(name, data) {
  fs.writeFileSync(path.join(EVIDENCE_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

function writeText(name, text) {
  fs.writeFileSync(path.join(EVIDENCE_DIR, name), text, "utf-8");
}

async function login(page) {
  const resp = await fetch(`${API_BASE}/api/v1/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (!resp.ok) {
    throw new Error(`Admin login failed ${resp.status}: ${await resp.text()}`);
  }
  const payload = await resp.json();
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((p) => {
    localStorage.setItem("token", p.access_token);
    localStorage.setItem("user_id", String(p.user_id));
    localStorage.setItem("user_name", p.full_name || "");
    localStorage.setItem("user_role", p.role || "");
    localStorage.setItem("user_avatar", p.avatar_url || "");
    localStorage.setItem("session_token", p.session_token || "");
    localStorage.setItem("user", JSON.stringify(p));
  }, payload);
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(`[console.error] ${msg.text()}`);
  });
  page.on("pageerror", (err) => consoleErrors.push(`[pageerror] ${String(err)}`));

  await login(page);

  const routes = (navManifest.nav_items || [])
    .filter((x) => x.type === "link" && x.href)
    .map((x) => ({ label: x.label, href: x.href }));

  const results = [];
  for (const route of routes) {
    const apiCalls = [];
    const failedRequests = [];

    const onResponse = (res) => {
      const url = res.url();
      if (url.includes("/api/")) {
        apiCalls.push({ url, status: res.status() });
      }
    };
    const onRequestFailed = (req) => {
      const url = req.url();
      if (!url.includes("/api/")) return;
      const failure = req.failure()?.errorText || "failed";
      failedRequests.push({ url, failure });
    };

    page.on("response", onResponse);
    page.on("requestfailed", onRequestFailed);

    let mainStatus = null;
    let ok = true;
    try {
      const resp = await page.goto(`${BASE_URL}${route.href}`, { waitUntil: "domcontentloaded", timeout: 60000 });
      mainStatus = resp?.status() ?? null;
      await page.waitForTimeout(2500);
      if (!(mainStatus === 200 || (mainStatus >= 300 && mainStatus < 400))) ok = false;
    } catch (err) {
      ok = false;
      mainStatus = -1;
      consoleErrors.push(`[route_error] ${route.href} ${String(err)}`);
    }

    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);

    const badApiCalls = apiCalls.filter((x) => !(x.status === 200 || (x.status >= 300 && x.status < 400)));
    const hardFailedRequests = failedRequests.filter((x) => x.failure !== "net::ERR_ABORTED");
    if (badApiCalls.length || hardFailedRequests.length) ok = false;

    results.push({
      label: route.label,
      route: route.href,
      main_status: mainStatus,
      ok,
      bad_api_calls: badApiCalls,
      failed_requests: hardFailedRequests,
      api_call_count: apiCalls.length,
    });
  }

  const summary = {
    total: results.length,
    ok: results.filter((r) => r.ok).length,
    failed: results.filter((r) => !r.ok).length,
    failures: results.filter((r) => !r.ok).map((r) => r.route),
  };

  writeJson("admin_routes_smoke.json", results);
  writeJson("admin_routes_smoke_summary.json", summary);
  writeText("admin_console_errors.txt", consoleErrors.join("\n"));

  await context.close();
  await browser.close();

  if (summary.failed > 0) process.exit(2);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
