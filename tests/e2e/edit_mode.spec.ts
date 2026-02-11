import { test, expect } from "@playwright/test";

const STUDENT_EMAIL = process.env.E2E_STUDENT_EMAIL || "admin@uask.ai";
const STUDENT_PASSWORD = process.env.E2E_STUDENT_PASSWORD || "DevOnlyChangeMe123!";
const API_BASE_URL = process.env.PLAYWRIGHT_API_BASE_URL || "http://localhost:9000";

async function getToken(request: any): Promise<string> {
    const resp = await request.post(`${API_BASE_URL}/api/v1/login`, {
        data: { email: STUDENT_EMAIL, password: STUDENT_PASSWORD },
    });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    return data.access_token;
}

test.describe("edit mode", () => {
    test("loads edit page, switches tabs, autosaves, and renders MathJax", async ({ page, request }) => {
        const token = await getToken(request);
        const seedResp = await request.post(`${API_BASE_URL}/api/v1/debug/chat_seed`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        expect(seedResp.ok()).toBeTruthy();
        const seedData = await seedResp.json();
        const sessionId = seedData.session_id;

        await page.goto(`/login`);
        await page.addStyleTag({ content: "nextjs-portal{display:none !important;}" });
        await page.locator('input[type="email"]').fill(STUDENT_EMAIL);
        await page.locator('input[type="password"]').fill(STUDENT_PASSWORD);
        await page.getByRole("button", { name: /log in/i }).click({ force: true });
        await page.waitForURL(/\/solve/);

        await page.goto(`/edit/${sessionId}`);
        await expect(page.getByText("Edit & Notes")).toBeVisible();

        await page.getByRole("button", { name: "My Edited Copy" }).click();
        await expect(page.getByText("Preview")).toBeVisible();

        await page.getByRole("button", { name: "Inline $...$" }).click();
        await page.getByRole("button", { name: "Block $$...$$" }).click();

        await expect(page.getByText(/Saved|Saving\.\.\./)).toBeVisible();

        await page.getByRole("button", { name: "My Notes" }).click();
        const notesEditor = page.locator("[contenteditable='true']").first();
        await notesEditor.click();
        await notesEditor.fill("My notes on the solution.");
        await expect(page.getByText(/Saved|Saving\.\.\./)).toBeVisible();

        await page.getByRole("button", { name: "My Edited Copy" }).click();
        const mathOutput = page.locator("mjx-container, .math-fallback");
        await expect(mathOutput.first()).toBeVisible({ timeout: 15000 });
    });
});
