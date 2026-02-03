import { expect, test } from "@playwright/test";

test.describe("Math Canvas exports", () => {
  test("shows clean export actions and triggers PDF print popup", async ({ page }) => {
    await page.goto("/chat/158");

    const exportPdf = page.getByRole("button", { name: "Export PDF" });
    await expect(exportPdf).toBeVisible();

    const popupPromise = page.waitForEvent("popup");
    await exportPdf.click();
    const popup = await popupPromise;
    await popup.waitForLoadState("domcontentloaded");
    await expect(popup).toHaveURL(/about:blank/);
  });

  test("triggers DOCX download", async ({ page }) => {
    await page.goto("/chat/158");

    const exportDocx = page.getByRole("button", { name: "Export DOCX" });
    await expect(exportDocx).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await exportDocx.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^uask-solution-.*\.docx$/);
  });
});
