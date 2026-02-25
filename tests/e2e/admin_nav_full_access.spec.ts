import { expect, test } from "@playwright/test";
import navManifest from "../../admin_nav_manifest.json";

const FRONTEND_BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_BASE = process.env.E2E_BACKEND_URL || "http://127.0.0.1:9000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "e2e.admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_DEFAULT_PASSWORD || "admin1234";

type NavItem = {
  type?: string;
  href?: string;
  label?: string;
};

async function loginAsAdmin(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const loginRes = await request.post(`${BACKEND_BASE}/api/v1/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  expect(loginRes.ok(), `login failed for ${ADMIN_EMAIL}`).toBeTruthy();
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
}

test("admin can open every admin nav tab and sees standardized header", async ({ page, request }) => {
  test.setTimeout(300000);
  await loginAsAdmin(page, request);

  const navItems = ((navManifest as { nav_items?: NavItem[] }).nav_items || []).filter(
    (x) => x.type === "link" && !!x.href && String(x.href).startsWith("/admin"),
  );

  for (const item of navItems) {
    const href = String(item.href);
    const label = item.label || href;
    await page.goto(`${FRONTEND_BASE}${href}`, { waitUntil: "domcontentloaded" });
    await expect(page, `${label} redirected to login`).not.toHaveURL(/\/login/);
    await expect(page.locator("[data-testid='admin-page-intro']"), `${label} missing admin page intro`).toBeVisible();
    await expect(page.locator("[data-testid='admin-page-intro']")).toContainText(/what you can do here/i);
    await expect(page.getByText(/access denied|forbidden/i).first(), `${label} shows access denied for admin`).toBeHidden();
  }
});
