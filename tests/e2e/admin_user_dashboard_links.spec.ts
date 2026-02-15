import { expect, test } from "@playwright/test";
import navManifest from "../../admin_nav_manifest.json";

const FRONTEND_BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_BASE = process.env.E2E_BACKEND_URL || "http://127.0.0.1:9000";

type NavItem = {
  type?: string;
  href?: string;
  label?: string;
  api_checks?: string[];
};

async function login(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
  email: string,
  password: string,
) {
  const loginRes = await request.post(`${BACKEND_BASE}/api/v1/login`, {
    data: { email, password },
  });
  expect(loginRes.ok(), `login failed for ${email}`).toBeTruthy();
  const data = (await loginRes.json()) as {
    access_token: string;
    user_id: number;
    full_name: string;
    role: string;
    avatar_url?: string;
    session_token?: string;
  };
  await page.goto(`${FRONTEND_BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((payload) => {
    localStorage.setItem("token", payload.access_token);
    localStorage.setItem("user_id", String(payload.user_id));
    localStorage.setItem("user_name", payload.full_name || "");
    localStorage.setItem("user_role", payload.role || "");
    localStorage.setItem("user_avatar", payload.avatar_url || "");
    localStorage.setItem("session_token", payload.session_token || "");
    localStorage.setItem("user", JSON.stringify(payload));
  }, data);
  await page.goto(`${FRONTEND_BASE}/solve`, { waitUntil: "domcontentloaded" });
  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token).toBeTruthy();
  return String(token);
}

function collectHardFailures(page: import("@playwright/test").Page) {
  const failures: string[] = [];
  const onResponse = (response: import("@playwright/test").Response) => {
    const url = response.url();
    if (!url.includes("/api/")) return;
    const status = response.status();
    if (status >= 500 || status === 404) {
      failures.push(`${status} ${url}`);
    }
  };
  page.on("response", onResponse);
  return {
    failures,
    stop: () => page.off("response", onResponse),
  };
}

test("admin dashboard routes and api links are not broken", async ({ page, request }) => {
  test.setTimeout(240000);
  const token = await login(page, request, "admin@uask.ai", "admin1234");
  await page.goto(`${FRONTEND_BASE}/admin/dashboard`, { waitUntil: "domcontentloaded" });
  await expect(page).not.toHaveURL(/\/login/);

  const items = ((navManifest as { nav_items?: NavItem[] }).nav_items || []).filter(
    (x) => x.type === "link" && !!x.href,
  );

  for (const item of items) {
    const href = String(item.href);
    const label = item.label || href;
    const tracker = collectHardFailures(page);
    await page.goto(`${FRONTEND_BASE}${href}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);
    tracker.stop();

    expect.soft(page.url(), `route redirected to login for ${label}`).not.toContain("/login");
    expect.soft(tracker.failures, `api failures while rendering ${label}`).toEqual([]);

    const checks = (item.api_checks || []).filter(Boolean);
    for (const path of checks) {
      const api = `${BACKEND_BASE}${path}`;
      const res = await request.get(api, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect.soft(res.status(), `${label} api_check failed: ${path}`).toBeLessThan(400);
    }
  }
});

test("user dashboard routes are not broken", async ({ page, request }) => {
  test.setTimeout(120000);
  await login(page, request, "student@uask.ai", "admin1234");
  const routes = [
    "/solve",
    "/dashboard",
    "/dashboard?tab=history",
    "/dashboard?tab=bookmarked",
    "/profile",
    "/billing",
  ];

  for (const route of routes) {
    const tracker = collectHardFailures(page);
    await page.goto(`${FRONTEND_BASE}${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(400);
    tracker.stop();
    expect.soft(page.url(), `route redirected to login for ${route}`).not.toContain("/login");
    expect.soft(tracker.failures, `api failures while rendering ${route}`).toEqual([]);
  }
});
