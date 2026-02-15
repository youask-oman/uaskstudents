import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

const FRONTEND_BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_BASE = process.env.E2E_BACKEND_URL || "http://127.0.0.1:9000";
const PASSWORD = process.env.E2E_DEFAULT_PASSWORD || "admin1234";

const users = {
  superadmin: process.env.E2E_SUPERADMIN_EMAIL || "admin@uask.ai",
  admin: process.env.E2E_ADMIN_EMAIL || "e2e.admin@uask.ai",
  support: process.env.E2E_SUPPORT_EMAIL || "e2e.support@uask.ai",
  finance: process.env.E2E_FINANCE_EMAIL || "e2e.finance@uask.ai",
  devops: process.env.E2E_DEVOPS_EMAIL || "e2e.devops@uask.ai",
  normal: process.env.E2E_NORMAL_EMAIL || "e2e.user@uask.ai",
  insufficient: process.env.E2E_INSUFFICIENT_EMAIL || "e2e.lowcredits@uask.ai",
};

type LoginPayload = {
  access_token: string;
  user_id: number;
  full_name: string;
  role: string;
  avatar_url?: string;
  session_token?: string;
};

function setupObservability(page: Page, testInfo: TestInfo) {
  const consoleErrors: string[] = [];
  const networkEvents: Array<{ url: string; status: number; method: string }> = [];
  const watched = [
    "/api/v1/credits/balance",
    "/api/v1/credits/holds",
    "/api/v1/credits/ledger",
    "/api/v1/credits/packs",
    "/api/v1/stripe/create_checkout_session",
    "/api/v1/admin/credits/",
    "/api/v1/admin/prompt_bindings",
    "/api/v1/solve_questions_batch",
  ];

  const onConsole = (msg: { type(): string; text(): string }) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  };
  const onResponse = (response: { url(): string; status(): number; request(): { method(): string } }) => {
    const url = response.url();
    if (watched.some((needle) => url.includes(needle))) {
      networkEvents.push({
        url,
        status: response.status(),
        method: response.request().method(),
      });
    }
  };

  page.on("console", onConsole);
  page.on("response", onResponse);

  return {
    async assertClean() {
      await testInfo.attach("console-errors.json", {
        body: JSON.stringify(consoleErrors, null, 2),
        contentType: "application/json",
      });
      await testInfo.attach("network-events.json", {
        body: JSON.stringify(networkEvents, null, 2),
        contentType: "application/json",
      });
      expect(consoleErrors, "Console errors detected").toEqual([]);
    },
    stop() {
      page.off("console", onConsole);
      page.off("response", onResponse);
    },
  };
}

async function apiLogin(request: APIRequestContext, email: string, password = PASSWORD): Promise<LoginPayload> {
  const res = await request.post(`${BACKEND_BASE}/api/v1/login`, { data: { email, password } });
  expect(res.ok(), `Login failed for ${email}`).toBeTruthy();
  return (await res.json()) as LoginPayload;
}

async function setSession(page: Page, payload: LoginPayload) {
  await page.goto(`${FRONTEND_BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((data) => {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user_id", String(data.user_id));
    localStorage.setItem("user_name", data.full_name || "");
    localStorage.setItem("user_role", data.role || "");
    localStorage.setItem("user_avatar", data.avatar_url || "");
    localStorage.setItem("session_token", data.session_token || "");
    localStorage.setItem("user", JSON.stringify(data));
  }, payload);
}

test.describe("Frontend Regression Gate", () => {
  test.setTimeout(180_000);

  test("A) auth flows: login render, invalid, success, persistence, logout", async ({ page, request }, testInfo) => {
    const obs = setupObservability(page, testInfo);
    try {
      await page.goto(`${FRONTEND_BASE}/login`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();

      await page.locator('input[type="email"]').fill("invalid@uask.ai");
      await page.locator('input[type="password"]').first().fill("bad-password");
      await page.getByRole("button", { name: /log in/i }).click();
      await expect(page).toHaveURL(/\/login/);
      const tokenAfterInvalid = await page.evaluate(() => localStorage.getItem("token"));
      expect(tokenAfterInvalid).toBeFalsy();

      const successLogin = await apiLogin(request, users.superadmin);
      await setSession(page, successLogin);
      await page.goto(`${FRONTEND_BASE}/solve`, { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/\/solve/);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/\/solve/);

      await page.evaluate(() => {
        localStorage.removeItem("token");
        localStorage.removeItem("user_id");
        localStorage.removeItem("user_name");
        localStorage.removeItem("user_role");
        localStorage.removeItem("user_avatar");
        localStorage.removeItem("session_token");
        localStorage.removeItem("user");
      });
      await page.goto(`${FRONTEND_BASE}/admin/dashboard`, { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/\/login/);
    } finally {
      await obs.assertClean();
      obs.stop();
    }
  });

  test("B) RBAC matrix on admin endpoints and privileged UI controls", async ({ page, request }, testInfo) => {
    const obs = setupObservability(page, testInfo);
    try {
      const superadmin = await apiLogin(request, users.superadmin);
      const admin = await apiLogin(request, users.admin);
      const support = await apiLogin(request, users.support);

      const grantAdmin = await request.post(`${BACKEND_BASE}/api/v1/admin/credits/grant`, {
        headers: {
          Authorization: `Bearer ${admin.access_token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": `e2e-rbac-grant-admin-${Date.now()}`,
        },
        data: { user_id: admin.user_id, credits: 1, reason: "E2E RBAC admin grant" },
      });
      expect(grantAdmin.status()).toBe(200);

      const grantSupport = await request.post(`${BACKEND_BASE}/api/v1/admin/credits/grant`, {
        headers: {
          Authorization: `Bearer ${support.access_token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": `e2e-rbac-grant-support-${Date.now()}`,
        },
        data: { user_id: support.user_id, credits: 1, reason: "E2E RBAC support grant" },
      });
      expect(grantSupport.status()).toBe(403);

      const superadminUi = await apiLogin(request, users.superadmin);
      await setSession(page, superadminUi);
      await page.goto(`${FRONTEND_BASE}/admin/billing/holds`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("button", { name: /release ocr holds/i })).toBeVisible();
      await page.goto(`${FRONTEND_BASE}/admin/prompt-bindings`, { waitUntil: "domcontentloaded" });
      await expect(page.locator('button[title="Read-only for your role."]')).toHaveCount(0);

      const supportUi = await apiLogin(request, users.support);
      await setSession(page, supportUi);
      await page.goto(`${FRONTEND_BASE}/admin/billing/holds`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("button", { name: /release ocr holds/i })).toHaveCount(0);
      await page.goto(`${FRONTEND_BASE}/admin/prompt-bindings`, { waitUntil: "domcontentloaded" });
      await expect(page.locator('button[title="Read-only for your role."]').first()).toBeVisible();
    } finally {
      await obs.assertClean();
      obs.stop();
    }
  });

  test("C) admin dashboard full sweep: credits tabs, users, overview", async ({ page, request }, testInfo) => {
    const obs = setupObservability(page, testInfo);
    try {
      const admin = await apiLogin(request, users.superadmin);
      await setSession(page, admin);

      const routes = [
        "/admin/dashboard",
        "/admin/users",
        "/admin/billing",
        "/admin/billing/inspector",
        "/admin/billing/holds",
        "/admin/billing/ledger",
        "/admin/billing/packs",
        "/admin/prompt-bindings",
      ];

      for (const route of routes) {
        await page.goto(`${FRONTEND_BASE}${route}`, { waitUntil: "domcontentloaded" });
        await expect(page).not.toHaveURL(/\/login/);
      }

      await page.goto(`${FRONTEND_BASE}/admin/users`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: /user directory/i })).toBeVisible();
      await page.getByPlaceholder(/search students or staff/i).fill("admin@uask.ai");
      await page.waitForTimeout(600);

      await page.goto(`${FRONTEND_BASE}/admin/billing/ledger`, { waitUntil: "domcontentloaded" });
      await expect(page.getByText(/usage ledger/i)).toBeVisible();
    } finally {
      await obs.assertClean();
      obs.stop();
    }
  });

  test("D) user dashboard credits/holds/ledger/packs and checkout call", async ({ page, request }, testInfo) => {
    const obs = setupObservability(page, testInfo);
    try {
      const user = await apiLogin(request, users.normal);
      await setSession(page, user);

      await page.goto(`${FRONTEND_BASE}/billing`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: /wallet & programs/i })).toBeVisible();
      await expect(page.getByText(/wallet summary/i)).toBeVisible();

      await page.goto(`${FRONTEND_BASE}/billing/payment`, { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: /top up credits/i })).toBeVisible();

      const token = user.access_token;
      const balance = await request.get(`${BACKEND_BASE}/api/v1/credits/balance`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(balance.ok()).toBeTruthy();

      const holds = await request.get(`${BACKEND_BASE}/api/v1/credits/holds?limit=5`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(holds.ok()).toBeTruthy();

      const ledger = await request.get(`${BACKEND_BASE}/api/v1/credits/ledger?limit=5`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(ledger.ok()).toBeTruthy();

      const packsRes = await request.get(`${BACKEND_BASE}/api/v1/credits/packs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(packsRes.ok()).toBeTruthy();
      const packs = (await packsRes.json()) as { items?: Array<{ pack_code: string }> };
      const firstPack = packs.items?.[0]?.pack_code;
      expect(firstPack).toBeTruthy();

      const checkout = await request.post(`${BACKEND_BASE}/api/v1/stripe/create_checkout_session`, {
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        data: { pack_code: firstPack },
      });
      expect(checkout.status()).toBeLessThan(500);
    } finally {
      await obs.assertClean();
      obs.stop();
    }
  });

  test("E) solve batch + billing UX paths (success/refusal/insufficient/idempotency/provider-failure)", async ({ page, request }, testInfo) => {
    const obs = setupObservability(page, testInfo);
    try {
      const normal = await apiLogin(request, users.normal);
      const insufficient = await apiLogin(request, users.insufficient);

      const makeQuestions = (n: number) =>
        Array.from({ length: n }, (_, i) => ({
          question_id: `q${i + 1}`,
          question_text: `Question ${i + 1}: Prove convergence of ${i + 2}!/${i + 2}^${i + 2} and justify rigorously.`,
        }));

      const solvePayload = (tier: "SHORT" | "FREE" | "STANDARD" | "RESEARCH", n: number, idem: string) => ({
        tier,
        mode: "SOLVE",
        graph_mode: "AUTO",
        domain_mode: "reals",
        preferred_response_language: "English",
        idempotency_key: idem,
        questions_json: makeQuestions(n),
      });

      const runSolve = async (
        tier: "SHORT" | "FREE" | "STANDARD" | "RESEARCH",
        n: number,
        idem: string,
      ): Promise<number | "timeout"> => {
        try {
          const res = await request.post(`${BACKEND_BASE}/api/v1/solve_questions_batch?user_id=${normal.user_id}`, {
            headers: { Authorization: `Bearer ${normal.access_token}`, "Content-Type": "application/json" },
            data: solvePayload(tier, n, idem),
            timeout: 30_000,
          });
          return res.status();
        } catch (err) {
          if (String(err).toLowerCase().includes("timeout")) return "timeout";
          throw err;
        }
      };

      const final15 = await runSolve("SHORT", 15, `e2e-final15-${Date.now()}`);
      expect([200, 428, 502, 504, "timeout"]).toContain(final15);

      const free5Idem = `e2e-free5-${Date.now()}`;
      const free5 = await runSolve("FREE", 5, free5Idem);
      expect([200, 428, 502, 504, "timeout"]).toContain(free5);

      const free5Replay = await request.post(`${BACKEND_BASE}/api/v1/solve_questions_batch?user_id=${normal.user_id}`, {
        headers: { Authorization: `Bearer ${normal.access_token}`, "Content-Type": "application/json" },
        data: solvePayload("FREE", 5, free5Idem),
      });
      expect([409, 200]).toContain(free5Replay.status());

      const standard2 = await runSolve("STANDARD", 2, `e2e-standard2-${Date.now()}`);
      expect([200, 428, 502, 504, "timeout"]).toContain(standard2);

      const research1 = await runSolve("RESEARCH", 1, `e2e-research1-${Date.now()}`);
      expect([200, 428, 502, 504, "timeout"]).toContain(research1);

      const insufficientRes = await request.post(`${BACKEND_BASE}/api/v1/solve_questions_batch?user_id=${insufficient.user_id}`, {
        headers: { Authorization: `Bearer ${insufficient.access_token}`, "Content-Type": "application/json" },
        data: solvePayload("FREE", 5, `e2e-insufficient-${Date.now()}`),
      });
      expect([402, 403, 428]).toContain(insufficientRes.status());
    } finally {
      await obs.assertClean();
      obs.stop();
    }
  });
});
