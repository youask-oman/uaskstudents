import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "admin1234";

const EVIDENCE_DIR = path.resolve("reports/evidence");
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

function writeJson(fileName, data) {
  fs.writeFileSync(path.join(EVIDENCE_DIR, fileName), JSON.stringify(data, null, 2), "utf-8");
}

function writeText(fileName, text) {
  fs.writeFileSync(path.join(EVIDENCE_DIR, fileName), text, "utf-8");
}

function parseSseDonePayload(rawText) {
  if (!rawText || typeof rawText !== "string") return null;
  const chunks = rawText.split("\n\n");
  let lastDone = null;
  for (const chunk of chunks) {
    const lines = chunk.split("\n").map((l) => l.trim());
    const evt = lines.find((l) => l.startsWith("event:"))?.replace("event:", "").trim();
    if (evt !== "done") continue;
    const dataLine = lines.find((l) => l.startsWith("data:"));
    if (!dataLine) continue;
    const rawJson = dataLine.replace(/^data:\s*/, "");
    try {
      lastDone = JSON.parse(rawJson);
    } catch {
      // ignore malformed fragments
    }
  }
  return lastDone;
}

async function bootstrapAuth(page) {
  let data = null;
  let lastErr = null;
  for (let i = 0; i < 10; i += 1) {
    try {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 15000);
      const resp = await fetch(`${API_BASE}/api/v1/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
        signal: controller.signal,
      });
      clearTimeout(t);
      if (resp.ok) {
        data = await resp.json();
        break;
      }
      lastErr = new Error(`Login API failed: ${resp.status} ${await resp.text()}`);
    } catch (err) {
      lastErr = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  if (!data) {
    throw lastErr || new Error("Login API failed");
  }
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((payload) => {
    localStorage.setItem("token", payload.access_token);
    localStorage.setItem("user_id", String(payload.user_id));
    localStorage.setItem("user_name", payload.full_name || "");
    localStorage.setItem("user_role", payload.role || "");
    localStorage.setItem("user_avatar", payload.avatar_url || "");
    localStorage.setItem("session_token", payload.session_token || "");
    localStorage.setItem("user", JSON.stringify(payload));
  }, data);
  await page.goto(`${BASE_URL}/solve`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
}

async function setSolveTier(page, tierLabel = "Standard") {
  await page.evaluate((tier) => {
    localStorage.setItem("uask.solveTier", tier.toUpperCase());
  }, tierLabel);
  await page.reload({ waitUntil: "networkidle" });
}

async function runSolveCapture(page, queryText, outRequestFile, outResponseFile, options = {}) {
  const captures = {
    requestPayload: null,
    responseRaw: null,
    donePayload: null,
  };

  const onRequest = (req) => {
    const url = req.url();
    if (url.includes("/api/v1/solve_v3_stream") && req.method() === "POST") {
      const pd = req.postData();
      if (pd) {
        try {
          captures.requestPayload = JSON.parse(pd);
        } catch {
          captures.requestPayload = { raw: pd };
        }
      }
    }
  };

  const onResponse = async (res) => {
    const url = res.url();
    if (url.includes("/api/v1/solve_v3_stream")) {
      try {
        const body = await res.text();
        captures.responseRaw = body;
        captures.donePayload = parseSseDonePayload(body);
      } catch {
        // ignore
      }
    }
  };

  page.on("request", onRequest);
  page.on("response", onResponse);

  await page.goto(`${BASE_URL}/solve`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // Try to accept legal modal if present.
  const acceptBtn = page.getByRole("button", { name: /^accept$/i });
  if (await acceptBtn.count()) {
    await acceptBtn.first().click();
    await page.waitForTimeout(1200);
  }

  const textarea = page.locator("[data-testid='solve-query-textarea']").first();
  if (await textarea.count()) {
    await textarea.waitFor({ timeout: 120000 });
    await textarea.fill(queryText);
  } else {
    const editable = page.locator("[contenteditable='true']").first();
    await editable.waitFor({ timeout: 120000 });
    await editable.click();
    await page.keyboard.press("Control+A");
    await page.keyboard.type(queryText);
  }

  if (options.ensureGraphAuto) {
    const autoButton = page.getByRole("button", { name: /^auto$/i });
    if (await autoButton.count()) {
      await autoButton.first().click();
    }
  }

  const solveBtn = page.locator("[data-testid='solve-submit-button']");
  await solveBtn.click();

  await page.waitForTimeout(options.waitMs ?? 35000);

  page.off("request", onRequest);
  page.off("response", onResponse);

  writeJson(outRequestFile, captures.requestPayload || {});
  writeJson(outResponseFile, captures.donePayload || { raw_stream: captures.responseRaw || "" });
  return captures;
}

async function captureChatArtifacts(browser, consoleLogsOutFile, harOutFile) {
  const context = await browser.newContext({
    recordHar: {
      path: path.join(EVIDENCE_DIR, "chat_page_network.har"),
      content: "embed",
    },
  });
  const page = await context.newPage();
  const consoleLines = [];
  page.on("console", (msg) => consoleLines.push(`[${msg.type()}] ${msg.text()}`));
  page.on("pageerror", (err) => consoleLines.push(`[pageerror] ${String(err)}`));

  await bootstrapAuth(page);

  // Resolve an existing chat id from backend history.
  const userId = await page.evaluate(() => localStorage.getItem("user_id") || "");
  const historyResp = await page.request.get(`${API_BASE}/api/v1/history?user_id=${encodeURIComponent(userId)}&saved_only=false`);
  let chatId = null;
  if (historyResp.ok()) {
    const h = await historyResp.json();
    if (Array.isArray(h) && h.length > 0) {
      chatId = h[0]?.id || h[0]?.session_id || null;
    }
  }
  if (!chatId) {
    // fallback to solve page if no history
    await page.goto(`${BASE_URL}/solve`, { waitUntil: "networkidle" });
  } else {
    await page.goto(`${BASE_URL}/chat/${chatId}`, { waitUntil: "networkidle" });
    // send one simple message if textbox exists
    const input = page.locator("textarea").first();
    if (await input.count()) {
      await input.fill("Test message from integration check");
      const sendBtn = page.getByRole("button", { name: /send|solve|submit/i }).first();
      if (await sendBtn.count()) {
        await sendBtn.click();
        await page.waitForTimeout(5000);
      }
    }
  }

  writeText(consoleLogsOutFile, consoleLines.join("\n"));
  await context.close();

  // Copy HAR with requested filename
  const harSrc = path.join(EVIDENCE_DIR, "chat_page_network.har");
  const harDst = path.join(EVIDENCE_DIR, harOutFile);
  if (fs.existsSync(harSrc)) {
    fs.copyFileSync(harSrc, harDst);
  } else {
    writeJson(harDst, { note: "HAR not generated" });
  }
}

async function crawlAdminRoutes(page) {
  const routes = [
    "/admin/dashboard",
    "/admin/prompt-bindings",
    "/admin/prompt-registry",
    "/admin/schema-registry",
    "/admin/system-config",
    "/admin/solver-attempts",
    "/admin/users",
    "/admin/whatsapp-bot",
    "/admin/ocr-configuration",
    "/admin/logs",
    "/admin/data",
    "/admin/jobs",
    "/admin/quotas",
    "/admin/promo-codes",
    "/admin/billing",
    "/admin/billing/pricing",
    "/admin/billing/programs",
    "/admin/billing/ledger",
  ];

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const results = [];
  for (const route of routes) {
    const apiStatuses = [];
    const listener = async (res) => {
      const url = res.url();
      if (url.includes("/api/")) {
        apiStatuses.push({ url, status: res.status() });
      }
    };
    page.on("response", listener);
    let mainStatus = null;
    let ok = true;
    try {
      const resp = await page.goto(`${BASE_URL}${route}`, { waitUntil: "networkidle", timeout: 45000 });
      mainStatus = resp?.status() ?? null;
      if (!(mainStatus === 200 || (mainStatus >= 300 && mainStatus < 400))) {
        ok = false;
      }
    } catch (err) {
      ok = false;
      mainStatus = -1;
    }
    page.off("response", listener);
    const badApis = apiStatuses.filter((x) => !(x.status === 200 || (x.status >= 300 && x.status < 400)));
    if (badApis.length > 0) ok = false;
    results.push({ route, main_status: mainStatus, ok, api_calls: apiStatuses });
  }

  writeJson("admin_routes_smoke.json", results);
  writeText("admin_console_errors.txt", consoleErrors.join("\n"));
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await bootstrapAuth(page);
  await setSolveTier(page, "STANDARD");

  // Scenario A: single solve success (also used for frontend payload artifacts)
  const single = await runSolveCapture(
    page,
    "Solve x^2 - 5x + 6 = 0 and include a plot of y=x^2-5x+6 showing x-intercepts.",
    "frontend_solve_request_payload.json",
    "frontend_solve_response_payload.json",
    { ensureGraphAuto: true, waitMs: 42000 }
  );

  // Scenario B: multi-question clarification
  await runSolveCapture(
    page,
    "1) Solve x^2 - 4 = 0\n\n2) Solve (x+1)/(x-2)=3",
    "frontend_multi_question_request_payload.json",
    "frontend_multi_question_response.json",
    { ensureGraphAuto: true, waitMs: 25000 }
  );

  // Scenario C: rapid repeat click / refresh behavior (for credit/idempotency evidence)
  const repeat = await runSolveCapture(
    page,
    "Solve x^2 - 9 = 0 and include a plot.",
    "frontend_repeat_click_request_payload.json",
    "frontend_repeat_click_response.json",
    { ensureGraphAuto: true, waitMs: 30000 }
  );
  await page.reload({ waitUntil: "networkidle" });
  const repeat2 = await runSolveCapture(
    page,
    "Solve x^2 - 9 = 0 and include a plot.",
    "frontend_repeat_refresh_request_payload.json",
    "frontend_repeat_refresh_response.json",
    { ensureGraphAuto: true, waitMs: 30000 }
  );

  writeJson("frontend_credit_scenario_ids.json", {
    caseA: {
      request: single.requestPayload,
      response: single.donePayload,
    },
    caseC: {
      request1: repeat.requestPayload,
      response1: repeat.donePayload,
      request2: repeat2.requestPayload,
      response2: repeat2.donePayload,
    },
  });

  await crawlAdminRoutes(page);
  await context.close();

  await captureChatArtifacts(browser, "chat_page_console_log.txt", "chat_page_network_har.json");

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
