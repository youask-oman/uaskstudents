import { test, expect } from "@playwright/test";

const STUDENT_EMAIL = process.env.E2E_STUDENT_EMAIL || "admin@uask.ai";
const STUDENT_PASSWORD = process.env.E2E_STUDENT_PASSWORD || "admin1234";
const API_BASE_URL = process.env.PLAYWRIGHT_API_BASE_URL || "http://127.0.0.1:9000";

async function getToken(request: any): Promise<string> {
  const resp = await request.post(`${API_BASE_URL}/api/v1/login`, {
    data: { email: STUDENT_EMAIL, password: STUDENT_PASSWORD },
  });
  expect(resp.ok()).toBeTruthy();
  const data = await resp.json();
  return data.access_token;
}

test.describe("mathjax parity", () => {
  test("chat and edit preview both typeset math", async ({ page, request }) => {
    const token = await getToken(request);
    const seedResp = await request.post(`${API_BASE_URL}/api/v1/debug/chat_seed`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    let sessionId: number | string | undefined;
    if (seedResp.ok()) {
      const seedData = await seedResp.json();
      sessionId = seedData.session_id;
    } else {
      sessionId = process.env.E2E_CHAT_SESSION_ID;
    }
    if (!sessionId) {
      throw new Error("debug chat seed failed and E2E_CHAT_SESSION_ID is not set");
    }

    await page.goto(`/login`);
    await page.addStyleTag({ content: "nextjs-portal{display:none !important;}" });
    await page.locator('input[type="email"]').fill(STUDENT_EMAIL);
    await page.locator('input[type="password"]').fill(STUDENT_PASSWORD);
    await page.getByRole("button", { name: /log in/i }).click({ force: true });
    await page.waitForURL(/\/solve/);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("mjx-container").first()).toBeVisible({ timeout: 15000 });

    await page.goto(`/edit/${sessionId}`);
    await expect(page.getByText("Edit & Notes")).toBeVisible();
    await expect(page.locator("mjx-container").first()).toBeVisible({ timeout: 15000 });
  });
});
