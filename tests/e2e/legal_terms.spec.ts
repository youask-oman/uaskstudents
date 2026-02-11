import { test, expect } from "@playwright/test";

test("terms page renders publicly", async ({ page }) => {
  await page.goto("/legal/terms");
  await expect(page.getByRole("heading", { name: "Terms of Service" })).toBeVisible();
  await expect(page.getByText("Effective date")).toBeVisible();
});
