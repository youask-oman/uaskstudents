import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: ["e2e/**/*.spec.{ts,js}", "tests/e2e/**/*.spec.{ts,js}"],
  timeout: 60_000,
  globalSetup: "tests/e2e/global.setup.ts",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || "test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: process.env.PLAYWRIGHT_HTML_REPORT || "playwright-report", open: "never" }],
    ["json", { outputFile: process.env.PLAYWRIGHT_JSON_REPORT || "test-results/playwright-report.json" }],
  ],
  fullyParallel: false,
  workers: process.env.CI ? 1 : 2,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "on-first-retry",
  },
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER === "1" ? undefined : {
    command: process.env.PLAYWRIGHT_WEBSERVER_CMD || "npm run dev:e2e",
    url: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 180_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
