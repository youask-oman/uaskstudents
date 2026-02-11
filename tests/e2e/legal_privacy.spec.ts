import { test, expect } from "@playwright/test";

test("privacy policy page renders publicly", async ({ page }) => {
  await page.goto("/legal/privacy");
  await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();
  await expect(page.getByText("Effective date")).toBeVisible();
});
