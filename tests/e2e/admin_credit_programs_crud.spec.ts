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
    const dir = path.join(process.cwd(), "reports", "screenshots");
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

test("admin credit programs CRUD", async ({ page }) => {
    await loginAsAdmin(page);

    await page.goto("/admin/billing/programs");
    await expect(page.getByText("Credit Programs")).toBeVisible();

    const stamp = Date.now();
    const slug = `pw-program-${stamp}`;
    const name = `PW Program ${stamp}`;
    const updatedName = `PW Program ${stamp} Updated`;

    await page.getByTestId("program-new").click();

    await page.getByTestId("program-slug").fill(slug);
    await page.getByTestId("program-name").fill(name);

    const numberInputs = page.locator('input[type="number"]');
    await numberInputs.nth(0).fill("25");
    await numberInputs.nth(1).fill("30");

    await page.getByTestId("program-reason").fill("Playwright create program");
    await page.getByTestId("program-submit").click();

    await expect(page.getByText("Program created")).toBeVisible();

    const row = page.locator("tr", { hasText: slug });
    await expect(row).toBeVisible();

    await row.locator('[data-testid^="program-edit-"]').first().click();

    await page.getByTestId("program-name").fill(updatedName);
    await page.getByTestId("program-reason").fill("Playwright update program");
    await page.getByTestId("program-submit").click();

    await expect(page.getByText("Program updated")).toBeVisible();

    const updatedRow = page.locator("tr", { hasText: slug });
    await updatedRow.locator('[data-testid^="program-archive-"]').first().click();

    await expect(page.getByText("Program archived")).toBeVisible();
    await expect(updatedRow).toContainText("archived");

    const shotsDir = ensureScreenshotsDir();
    await page.screenshot({ path: path.join(shotsDir, "admin-credit-programs-crud.png"), fullPage: true });
});
