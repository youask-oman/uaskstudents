const { expect, test } = require("@playwright/test");

test("Persistence Flow: Restore state on refresh (Mocked)", async ({ page }) => {
    // Mock user login
    await page.goto("/");
    await page.evaluate(() => {
        localStorage.setItem("user_id", "1");
    });

    await page.route("**/api/v1/attempt/*", async route => {
        const url = route.request().url();
        const attemptId = url.split('/').pop();
        if (attemptId === "mock-ambiguous-id") {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    status: "ambiguous",
                    error_message: "Please clarify: x+5 equals what?",
                    clarification_count: 1
                })
            });
        }
    });

    await page.route("**/api/v1/solve/clarify", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                status: "success",
                session_id: 456
            })
        });
    });

    // 1. Manually set localStorage to simulate an active ambiguous attempt
    await page.goto("/solve");
    await page.evaluate(() => {
        localStorage.setItem("uask.activeAttemptId", "mock-ambiguous-id");
        localStorage.setItem("uask.activeQuery", "x+5");
    });

    // 2. Refresh page to trigger restoration
    await page.reload();

    // 3. Expect restoration loading state then Clarification UI
    await expect(page.locator("text=Restoring session...")).toBeVisible();
    await expect(page.locator("text=Clarification Needed")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Please clarify: x+5 equals what?")).toBeVisible();

    // 4. Submit clarification (mocked to succeed)
    await page.getByPlaceholder("Provide more detail here...").fill("equals 10");
    await page.getByRole("button", { name: "Send Clarification" }).click();

    // 5. Expect redirect to chat (session 456 from mock)
    await expect(page).toHaveURL(/\/chat\/456/, { timeout: 10000 });

    // 6. Verify localStorage is cleared
    const clearedAttemptId = await page.evaluate(() => localStorage.getItem("uask.activeAttemptId"));
    expect(clearedAttemptId).toBeNull();
});
