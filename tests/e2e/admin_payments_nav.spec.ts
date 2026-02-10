import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@uask.ai";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "DevOnlyChangeMe123!";

async function loginAsAdmin(page: any) {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /log in/i }).click();
    await page.waitForURL(/\/solve/);
}

function ensureScreenshotsDir() {
    const dir = path.join(process.cwd(), "reports", "screenshots", "payments");
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

test("admin payments dashboard navigation", async ({ page }) => {
    await loginAsAdmin(page);

    await page.goto("/admin/dashboard");
    await expect(page.getByText("Analytics Dashboard")).toBeVisible();

    await page.getByRole("link", { name: "Payments" }).click();
    await expect(page).toHaveURL(/\/adminpayments/);

    const shotsDir = ensureScreenshotsDir();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(shotsDir, "overview.png"), fullPage: true });

    const tabs = [
        { name: "Requests", url: "/adminpayments?tab=requests" },
        { name: "Top-Ups", url: "/adminpayments/topups" },
        { name: "Legacy Subscriptions", url: "/adminpayments/subscriptions" },
        { name: "Invoices", url: "/adminpayments?tab=invoices" },
        { name: "Stripe Events", url: "/adminpayments?tab=stripe_events" },
        { name: "Reconciliation", url: "/adminpayments?tab=reconciliation" },
        { name: "Pricing", url: "/adminpayments?tab=pricing" },
        { name: "Payments Config", url: "/adminpayments/config" },
    ];

    for (const tab of tabs) {
        await page.goto(tab.url);
        await expect(page).not.toHaveURL(/404/);
        await page.waitForTimeout(500);
        const slug = tab.name.toLowerCase().replace(/\s+/g, "-");
        await page.screenshot({ path: path.join(shotsDir, `${slug}.png`), fullPage: true });
    }
});
