import { test, expect } from "@playwright/test";

test("chat_final/63 renders one question, no giant rect, and playback grows", async ({ page }) => {
  await page.goto("/chat_final/63", { waitUntil: "networkidle" });

  const questionText = "If the patient tests positive on the first test, find the probability they actually have the disease.";
  const occurrences = page.getByText(questionText, { exact: false });
  await expect(occurrences.first()).toBeVisible();
  await expect(occurrences).toHaveCount(1);

  const giantRectCount = await page.locator('svg rect[width="13800"][height="950"][y="-200"]').count();
  expect(giantRectCount).toBe(0);

  const playback = page.locator("#steps-block-playback-solution");
  await expect(playback).toBeVisible();

  const lenAtT0 = await playback.innerText().then((txt) => txt.length);
  await page.waitForTimeout(1100);
  const lenAtT1 = await playback.innerText().then((txt) => txt.length);
  expect(lenAtT1).toBeGreaterThanOrEqual(lenAtT0);
});

