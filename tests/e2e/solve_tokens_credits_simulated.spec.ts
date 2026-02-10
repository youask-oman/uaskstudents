import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import fs from "fs";
import path from "path";

const STUDENT_EMAIL = process.env.E2E_STUDENT_EMAIL || "admin@uask.ai";
const STUDENT_PASSWORD = process.env.E2E_STUDENT_PASSWORD || "DevOnlyChangeMe123!";

async function login(page: Page) {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill(STUDENT_EMAIL);
    await page.locator('input[type="password"]').fill(STUDENT_PASSWORD);
    await page.getByRole("button", { name: /log in/i }).click();
    await page.waitForURL(/\/solve/);
}

function ensureScreenshotsDir() {
    const dir = path.join(process.cwd(), "reports", "screenshots", "solve_simulated");
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

async function getWalletBalance(page: Page): Promise<number> {
    const res = await page.request.get("/api/v1/wallet/summary");
    expect(res.ok()).toBeTruthy();
    const payload = await res.json();
    return Number(payload.computed_balance ?? payload.credits_balance ?? 0);
}

async function runSolve(page: Page, tierLabel: string, expectedCharge: number) {
    await page.getByRole("button", { name: tierLabel }).click();
    await page.locator('textarea[placeholder="Type your question..."]').fill("Solve 2x + 3 = 11");
    await page.getByRole("button", { name: /^Solve$/ }).click();
    await expect(page.getByText("Simulated Solve Debug (DEV)")).toBeVisible();
    await expect(page.getByText("Input Tokens: 2000")).toBeVisible();
    await expect(page.getByText("Output Tokens: 1000")).toBeVisible();
    await expect(page.getByText("Cached Tokens: 250")).toBeVisible();
    await expect(page.getByText("Model: gpt-5-mini")).toBeVisible();
    await expect(page.getByText("Credits Charged: " + expectedCharge)).toBeVisible();
}

test.describe("solve tokens + credits (simulated)", () => {
    test.beforeEach(async ({ page }) => {
        await login(page);
        await page.getByText("Simulated Solve Debug (DEV)").waitFor({ state: "visible" });
        await page.getByLabel("Force Error").uncheck();
        await page.getByLabel("Reuse Idempotency Key").check();
        await page.getByLabel("Stay On Result").check();
    });

    test("three_step (free) charges 5 credits with simulated tokens", async ({ page }) => {
        const before = await getWalletBalance(page);
        await runSolve(page, "Free", 5);
        const after = await getWalletBalance(page);
        expect(before - after).toBe(5);
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "three_step.png"), fullPage: true });
    });

    test("short charges 7 credits", async ({ page }) => {
        const before = await getWalletBalance(page);
        await runSolve(page, "Short", 7);
        const after = await getWalletBalance(page);
        expect(before - after).toBe(7);
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "short.png"), fullPage: true });
    });

    test("standard charges 10 credits", async ({ page }) => {
        const before = await getWalletBalance(page);
        await runSolve(page, "Standard", 10);
        const after = await getWalletBalance(page);
        expect(before - after).toBe(10);
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "standard.png"), fullPage: true });
    });

    test("research charges 25 credits", async ({ page }) => {
        const before = await getWalletBalance(page);
        await runSolve(page, "Research", 25);
        const after = await getWalletBalance(page);
        expect(before - after).toBe(25);
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "research.png"), fullPage: true });
    });

    test("failure path releases hold and shows request id", async ({ page }) => {
        const before = await getWalletBalance(page);
        await page.getByLabel("Force Error").check();
        await page.getByRole("button", { name: "Free" }).click();
        await page.locator('textarea[placeholder="Type your question..."]').fill("Solve 2x + 3 = 11");
        await page.getByRole("button", { name: /^Solve$/ }).click();
        await expect(page.getByText("Error Code: simulated_error")).toBeVisible();
        await expect(page.getByText("Error Request ID:")).toBeVisible();
        const after = await getWalletBalance(page);
        expect(before - after).toBe(0);
        await page.getByLabel("Force Error").uncheck();
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "failure.png"), fullPage: true });
    });

    test("idempotency prevents double charge", async ({ page }) => {
        const before = await getWalletBalance(page);
        await page.getByRole("button", { name: "Free" }).click();
        await page.locator('textarea[placeholder="Type your question..."]').fill("Solve 2x + 3 = 11");
        await page.getByRole("button", { name: /^Solve$/ }).click();
        await expect(page.getByText("Credits Charged: 5")).toBeVisible();
        const firstAttemptId = await page.getByText(/Attempt ID:/).textContent();
        const mid = await getWalletBalance(page);
        await page.getByRole("button", { name: /^Solve$/ }).click();
        await expect(page.getByText("Credits Charged: 5")).toBeVisible();
        const secondAttemptId = await page.getByText(/Attempt ID:/).textContent();
        const after = await getWalletBalance(page);
        expect(mid - after).toBe(0);
        expect(firstAttemptId).toBe(secondAttemptId);
        expect(before - mid).toBe(5);
        const shotsDir = ensureScreenshotsDir();
        await page.screenshot({ path: path.join(shotsDir, "idempotency.png"), fullPage: true });
    });
});
