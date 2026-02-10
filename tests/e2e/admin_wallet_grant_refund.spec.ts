import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "DevOnlyChangeMe123!";
const API_BASE = process.env.PLAYWRIGHT_API_BASE_URL || "http://localhost:8000";

async function loginAsAdmin(page: any) {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /log in/i }).click();
    await page.waitForURL(/\/solve/);
}

function ensureScreenshotsDir() {
    const dir = path.join(process.cwd(), "reports", "screenshots");
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

test("admin wallet grant/refund updates lots + ledger", async ({ page, request }) => {
    await loginAsAdmin(page);

    const token = await page.evaluate(() => localStorage.getItem("token"));
    expect(token).toBeTruthy();

    const usersResp = await request.get(`${API_BASE}/api/v1/admin/users?limit=1`, {
        headers: { Authorization: `Bearer ${token}` },
    });
    expect(usersResp.ok()).toBeTruthy();
    const usersData = await usersResp.json();
    const userId = usersData.users[0].id;

    await page.goto(`/admin/users/${userId}`);
    await expect(page.getByText("User Profile")).toBeVisible();
    await page.getByRole("button", { name: "Wallet & Programs" }).click();
    await expect(page.getByText("Wallet Summary")).toBeVisible();

    const shotsDir = ensureScreenshotsDir();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(shotsDir, "admin-wallet-before.png"), fullPage: true });

    await page.getByTestId("wallet-grant-button").click();
    await expect(page.getByText("Grant Credits")).toBeVisible();
    await page.getByTestId("grant-amount").fill("10");
    await page.getByTestId("grant-reason").fill("Playwright grant test");
    await page.getByTestId("grant-submit").click();
    await expect(page.getByText("Credits granted")).toBeVisible();

    await page.getByTestId("wallet-refund-button").click();
    await expect(page.getByText("Issue Refund")).toBeVisible();
    await page.getByTestId("refund-amount").fill("10");
    await page.getByTestId("refund-reason").fill("Playwright refund test");
    await page.getByTestId("refund-submit").click();
    await expect(page.getByText("Refund issued")).toBeVisible();

    await expect(page.getByText("ADMIN_ADJUSTMENT")).toBeVisible();
    await expect(page.getByText("ADMIN_REFUND")).toBeVisible();
    await expect(page.getByText("ADJUSTMENT")).toBeVisible();
    await expect(page.getByText("REFUND")).toBeVisible();

    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(shotsDir, "admin-wallet-after.png"), fullPage: true });
});
