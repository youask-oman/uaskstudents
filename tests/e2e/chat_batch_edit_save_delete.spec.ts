import { expect, test } from "@playwright/test";

test("chat page non-demo batch supports step edit/save/delete and final save", async ({ page }) => {
  const runtimeErrors: string[] = [];
  const consoleErrors: string[] = [];

  page.on("pageerror", (err) => runtimeErrors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.addInitScript(() => {
    localStorage.setItem("user_id", "1");
    localStorage.setItem("token", "e2e-token");
  });

  await page.route("**/api/v1/sessions/789", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 789,
        title: "Batch solve (2)",
        subject: "Math",
        created_at: new Date().toISOString(),
        messages: [
          {
            id: "u1",
            role: "user",
            content: "Solve the selected questions:\n- (q1) Solve for x: sqrt(3x + 4) = 2\n- (q2) Factor completely: x^2 - 5x + 6",
            created_at: new Date().toISOString(),
          },
          {
            id: "a1",
            role: "assistant",
            content: "Batch response",
            created_at: new Date().toISOString(),
            structured_data: {
              mode: "batch_text_solve",
              requested_mode: "standard_detailed",
              response_language: "en",
              question_count: 2,
              solutions: [
                {
                  question_id: "q1",
                  steps: [{ title: "Square both sides", explanation: "3x + 4 = 4" }],
                  final_answer: { answer_text: "x = 0", answer_latex: "x=0", values: [] },
                },
                {
                  question_id: "q2",
                  steps: [{ title: "Find factors", explanation: "x^2 - 5x + 6 = (x-2)(x-3)" }],
                  final_answer: { answer_text: "(x-2)(x-3)", answer_latex: "(x-2)(x-3)", values: [] },
                },
              ],
            },
          },
        ],
      }),
    });
  });

  await page.goto("/chat/789");

  await expect(page.getByText("Question q1").first()).toBeVisible();
  await expect(page.getByText("Question q2").first()).toBeVisible();

  await page.getByTestId("step-edit-batch-steps-q1-1-0").click();
  const explanationEditor = page
    .getByTestId("step-explanation-editor-wrap-batch-steps-q1-1-0")
    .locator('[contenteditable="true"]')
    .first();
  await explanationEditor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("Updated step explanation for q1");
  await page.getByTestId("step-save-batch-steps-q1-1-0").click();
  await expect(page.getByText("Updated step explanation for q1")).toBeVisible();

  await page.getByTestId("step-delete-batch-steps-q1-1-0").click();
  await expect(page.getByTestId("step-edit-batch-steps-q1-1-0")).toHaveCount(0);
  await expect(page.getByText("Find factors").first()).toBeVisible();

  await page.getByTestId("final-edit-batch-steps-q2-2").click();
  const finalTextarea = page.locator("textarea").first();
  await finalTextarea.fill("x=42");
  await page.getByTestId("final-save-batch-steps-q2-2").click();
  await page.getByTestId("final-edit-batch-steps-q2-2").click();
  await expect(page.locator("textarea").first()).toHaveValue("x=42");

  const filteredRuntimeErrors = runtimeErrors.filter((msg) => !msg.includes("ResizeObserver loop limit exceeded"));
  const filteredConsoleErrors = consoleErrors.filter((msg) => !msg.includes("401 (Unauthorized)"));
  expect(filteredRuntimeErrors).toEqual([]);
  expect(filteredConsoleErrors).toEqual([]);
});
