import { expect, test } from "@playwright/test";

const TOKEN_POLICY_FIXTURE = {
  ok: true,
  policy: {
    text: {
      input_max: 6000,
      input_max_chars: 12000,
      output_max: {
        minimal: { solve: 1200, study: 1200 },
        detailed: { solve: 2400, study: 2400 },
      },
    },
    request: {
      system_and_schema_budget: 800,
      expected_output_budget: 1500,
    },
    ocr_image: { extract_max: 10, input_max: 6000, input_overhead: 200 },
    ocr_pdf: { extract_max: 10, input_max: 6000, input_overhead: 300 },
    voice: { input_max: 6000, input_overhead: 200 },
  },
};

const MULTI_INPUT = [
  "1) Solve for x: sqrt(3x + 4) = 2",
  "2) Factor completely: x^2 - 5x + 6",
  "3) Find the derivative: d/dx (x^3 * ln(x))",
].join("\n");

test("confirm-selected updates textbox, preview blocks separate, solve redirects to chat and sends batch payload", async ({ page }) => {
  const runtimeErrors: string[] = [];
  const consoleErrors: string[] = [];
  let batchCallCount = 0;
  let lastBatchPayload: Record<string, unknown> | null = null;

  page.on("pageerror", (err) => runtimeErrors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.addInitScript(() => {
    localStorage.setItem("user_id", "1");
    localStorage.setItem("uask.solveTier", "STANDARD");
    localStorage.setItem("token", "e2e-token");
  });

  // Fallback API stub to prevent unrelated 401s from auxiliary widgets.
  await page.route("**/api/v1/**", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  await page.route("**/api/v1/config/token-policy", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(TOKEN_POLICY_FIXTURE) });
  });
  await page.route("**/api/v1/history**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/api/v1/user/profile**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ is_public: false, school_name: "E2E School", profile_province_state: "CA", profile_country: "US" }),
    });
  });
  await page.route("**/api/v1/wallet/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user_id: 1,
        cached_balance: 500,
        computed_balance: 500,
        delta: 0,
        pending_holds: 0,
        pending_hold_credits: 0,
        expiring_soon_credits: 0,
        expiring_soon_lots: 0,
        entitlements: {},
        effective_tier: "RESEARCH",
        active_programs: [],
      }),
    });
  });
  await page.route("**/api/v1/wallet/programs**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }) });
  });
  await page.route("**/api/v1/credits/estimate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_credits: 75,
        per_question_credits: 25,
        breakdown: { base: 25, reason: "solve.research.text", addons: {} },
        cap_checks: { daily_ok: true, ocr_ok: true, voice_ok: true },
        pricing_version: "1",
        pricing_version_plan: "1",
        pricing_version_token_config: 1,
      }),
    });
  });
  await page.route("**/api/v1/math/solve_text_batch**", async (route) => {
    batchCallCount += 1;
    const request = route.request();
    lastBatchPayload = (await request.postDataJSON()) as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        request_id: "req-e2e",
        attempt_id: "attempt-e2e",
        requested_mode: "standard_detailed",
        schema_name: "solve_standard_detailed_v1",
        response_language: "en",
        question_count: 3,
        session_id: 456,
        telemetry: { tokens: { total: 321 }, latency_ms: 222 },
        solutions: [
          { question_id: "q1", steps: [{ title: "Step 1", explanation: "Square both sides" }], final_answer: { answer_text: "x = 0" } },
          { question_id: "q2", steps: [{ title: "Step 1", explanation: "Factor polynomial" }], final_answer: { answer_text: "(x-2)(x-3)" } },
          { question_id: "q3", steps: [{ title: "Step 1", explanation: "Use product rule" }], final_answer: { answer_text: "3x^2 ln(x) + x^2" } },
        ],
      }),
    });
  });
  await page.route("**/api/v1/sessions/456", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 456,
        title: "Batch solve (3)",
        subject: "Math",
        created_at: new Date().toISOString(),
        messages: [
          {
            id: "u1",
            role: "user",
            content: "Solve the selected questions:\n- (q1) Solve for x: sqrt(3x + 4) = 2\n- (q2) Factor completely: x^2 - 5x + 6\n- (q3) Find the derivative: d/dx (x^3 * ln(x))",
            created_at: new Date().toISOString(),
          },
          {
            id: "a1",
            role: "assistant",
            content: "Batch response",
            created_at: new Date().toISOString(),
            structured_data: {
              mode: "batch_text_solve",
              requested_mode: "research_detailed",
              response_language: "en",
              question_count: 3,
              solutions: [
                { question_id: "q1", steps: [{ title: "Step 1", explanation: "Square both sides" }], final_answer: { answer_text: "x = 0" } },
                { question_id: "q2", steps: [{ title: "Step 1", explanation: "Factor polynomial" }], final_answer: { answer_text: "(x-2)(x-3)" } },
                { question_id: "q3", steps: [{ title: "Step 1", explanation: "Use product rule" }], final_answer: { answer_text: "3x^2 ln(x) + x^2" } },
              ],
            },
          },
        ],
      }),
    });
  });

  await page.goto("/solve");

  await page.getByTestId("math-mode-toggle").click();
  const textarea = page.getByTestId("solve-query-textarea");
  await expect(textarea).toBeVisible();
  await textarea.fill(MULTI_INPUT);

  await page.getByRole("button", { name: /split/i }).click();
  await expect(page.getByTestId("split-modal")).toBeVisible();
  await page.getByTestId("split-confirm-selected").click();

  await expect(textarea).toContainText("1) Solve for x: sqrt(3x + 4) = 2");
  await expect(textarea).toContainText("2) Factor completely: x^2 - 5x + 6");
  await expect(textarea).toContainText("3) Find the derivative: d/dx (x^3 * ln(x))");

  const previewBlocks = page.getByTestId("live-math-preview-block");
  await expect(previewBlocks).toHaveCount(3);

  await page.getByTestId("solve-submit-button").click();
  await page.waitForURL("**/chat/456");

  await expect(page.getByText("Question q1").first()).toBeVisible();
  await expect(page.getByText("Question q2").first()).toBeVisible();
  await expect(page.getByText("Question q3").first()).toBeVisible();
  await expect(page.getByText("x = 0").first()).toBeVisible();
  await expect(page.getByText("(x-2)(x-3)")).toBeVisible();
  await expect(page.getByText("Use product rule")).toBeVisible();

  expect(batchCallCount).toBe(1);
  expect(lastBatchPayload).not.toBeNull();
  const sentQuestions = (lastBatchPayload?.questions || []) as Array<Record<string, unknown>>;
  expect(sentQuestions).toHaveLength(3);
  expect(sentQuestions.map((q) => q.question_id)).toEqual(["q1", "q2", "q3"]);

  const filteredRuntimeErrors = runtimeErrors.filter(
    (msg) =>
      !msg.includes("ResizeObserver loop limit exceeded") &&
      !msg.includes("Typesetting failed: Cannot read properties of null")
  );
  const filteredConsoleErrors = consoleErrors.filter(
    (msg) => !msg.includes("401 (Unauthorized)")
  );
  expect(filteredRuntimeErrors).toEqual([]);
  expect(filteredConsoleErrors).toEqual([]);
});
