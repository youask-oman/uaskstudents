import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "admin1234";
const EVIDENCE_DIR = path.resolve("reports/evidence");
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

async function login(page) {
  const resp = await fetch(`${API_BASE}/api/v1/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (!resp.ok) throw new Error(`login failed ${resp.status}`);
  const p = await resp.json();
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((u) => {
    localStorage.setItem("token", u.access_token);
    localStorage.setItem("user_id", String(u.user_id));
    localStorage.setItem("user_name", u.full_name || "");
    localStorage.setItem("user_role", u.role || "");
    localStorage.setItem("session_token", u.session_token || "");
    localStorage.setItem("user", JSON.stringify(u));
  }, p);
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const target = { label: "Question Identity", route: "/admin/cache/question-identity" };
  const apiCalls = [];
  const bad = [];

  await login(page);
  const onResponse = (res) => {
    const url = res.url();
    if (url.includes("/api/")) {
      const status = res.status();
      apiCalls.push({ url, status });
      if (!(status === 200 || (status >= 300 && status < 400))) bad.push({ url, status });
    }
  };
  page.on("response", onResponse);

  let mainStatus = null;
  let ok = true;
  try {
    const resp = await page.goto(`${BASE_URL}${target.route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    mainStatus = resp?.status() ?? null;
    await page.waitForTimeout(2500);
    if (!(mainStatus === 200 || (mainStatus >= 300 && mainStatus < 400))) ok = false;
  } catch {
    ok = false;
    mainStatus = -1;
  }
  page.off("response", onResponse);
  if (bad.length) ok = false;

  const result = { ...target, main_status: mainStatus, ok, bad_api_calls: bad, api_call_count: apiCalls.length };
  fs.writeFileSync(path.join(EVIDENCE_DIR, "admin_new_tab_question_identity_smoke.json"), JSON.stringify([result], null, 2), "utf-8");
  fs.writeFileSync(path.join(EVIDENCE_DIR, "admin_new_tab_question_identity_smoke_summary.json"), JSON.stringify({ total: 1, ok: ok ? 1 : 0, failed: ok ? 0 : 1 }, null, 2), "utf-8");

  await context.close();
  await browser.close();
  if (!ok) process.exit(2);
}

run().catch((e) => { console.error(e); process.exit(1); });
