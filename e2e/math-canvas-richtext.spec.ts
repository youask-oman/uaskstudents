import { expect, test } from "@playwright/test";

test.describe("Math Canvas rich text toolbar", () => {
  test("formats an active text block with headings, lists, links, and tables", async ({ page }) => {
    await page.goto("/chat/158");

    const canvas = page.locator("[data-testid^='paper-canvas-']").first();
    await page.getByRole("button", { name: "Text" }).click();
    await canvas.click({ position: { x: 120, y: 140 } });

    const styleSelect = page.getByLabel("Text style");
    await expect(styleSelect).toBeEnabled();

    const editor = page.locator(".canvasRichTextEditorWrap .ProseMirror").first();
    await editor.click();
    await page.keyboard.press("Control+A");
    await page.keyboard.type("Rich text demo");

    await styleSelect.selectOption("title");
    await expect(editor.locator("h1")).toContainText("Rich text demo");

    await page.getByLabel("List style").selectOption("bulleted");
    await expect(editor.locator("ul li").first()).toContainText("Rich text demo");

    await editor.click();
    await page.keyboard.press("Control+A");
    await page.getByLabel("Link").click();
    await page.getByPlaceholder("https://example.com").fill("uask.ai");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(editor.locator("a[href^='https://uask.ai']")).toHaveCount(1);

    await page.getByLabel("Table").click();
    await page.getByRole("button", { name: "Insert 3x3 table" }).click();
    await expect(editor.locator("table")).toHaveCount(1);
  });
});

