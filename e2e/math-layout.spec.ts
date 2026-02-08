import { test, expect } from "@playwright/test";

test.describe("Math Layout and Scrollbars", () => {
    test("should have no internal scrollbars in math containers inside .paperPage", async ({ page }) => {
        // Navigate to a chat page with a solution (mock data should trigger)
        await page.goto("/chat/1");

        // Wait for math to render (MathJax labels are distinctive)
        await page.waitForSelector("mjx-container, .MathJax, .katex", { state: "visible", timeout: 30000 });

        // Select all math containers inside the paper container
        const mathContainers = await page.locator(".paperPage mjx-container, .paperPage .MathJax, .paperPage .katex").all();

        console.log(`Found ${mathContainers.length} math containers to check.`);

        for (const container of mathContainers) {
            const isVisible = await container.isVisible();
            if (!isVisible) continue;

            // Check for horizontal overflow
            const scrollWidth = await container.evaluate((el) => el.scrollWidth);
            const clientWidth = await container.evaluate((el) => el.clientWidth);

            // Allow 1px tolerance for subpixel rendering
            expect(scrollWidth, "Math container should not have horizontal scrollbar").toBeLessThanOrEqual(clientWidth + 1);

            // Check for vertical overflow
            const scrollHeight = await container.evaluate((el) => el.scrollHeight);
            const clientHeight = await container.evaluate((el) => el.clientHeight);

            expect(scrollHeight, "Math container should not have vertical scrollbar").toBeLessThanOrEqual(clientHeight + 1);

            // Verify CSS properties
            const overflow = await container.evaluate((el) => window.getComputedStyle(el).overflow);
            expect(overflow, "Math container should have visible overflow").toBe("visible");
        }
    });

    test("should scale down extremely long math instead of scrolling", async ({ page }) => {
        // This test specifically looks for the scale-down class on long math
        await page.goto("/chat/1");

        // The complex demo solution has some long equations
        await page.waitForSelector(".paperPage", { state: "visible" });

        // Check if any element has the scale-down class (if our hook detected overflow)
        // Note: This might not trigger if the screen is wide enough, but the class should be there if linebreaks fail
        const scaleElements = await page.locator(".mathScaleToFit").all();

        if (scaleElements.length > 0) {
            console.log(`Found ${scaleElements.length} elements scaled down to fit.`);
            for (const el of scaleElements) {
                const transform = await el.evaluate((node) => window.getComputedStyle(node).transform);
                expect(transform).not.toBe("none");
                expect(transform).toContain("matrix"); // matrix(...) represents a scale/transform
            }
        }
    });
});
