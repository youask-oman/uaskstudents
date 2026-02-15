import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function runStep(name, command, args, env, cwd, reportDir) {
  const outFile = path.join(reportDir, `${name}.stdout.log`);
  const errFile = path.join(reportDir, `${name}.stderr.log`);
  const result = spawnSync(command, args, {
    cwd,
    env: { ...process.env, ...env },
    encoding: "utf-8",
    shell: process.platform === "win32",
  });
  fs.writeFileSync(outFile, result.stdout || "", "utf-8");
  fs.writeFileSync(errFile, result.stderr || "", "utf-8");
  return result.status ?? 1;
}

const repoRoot = process.cwd();
const stamp = nowStamp();
const reportDir = path.join(repoRoot, "backend", "reports", "frontend_regression_gate", stamp);
fs.mkdirSync(reportDir, { recursive: true });

const playwrightOutput = path.join(reportDir, "playwright-output");
const playwrightHtml = path.join(reportDir, "playwright-html");
const playwrightJson = path.join(reportDir, "playwright-report.json");

const commonEnv = {
  PLAYWRIGHT_BASE_URL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",
  E2E_BACKEND_URL: process.env.E2E_BACKEND_URL || "http://127.0.0.1:9000",
  PLAYWRIGHT_OUTPUT_DIR: playwrightOutput,
  PLAYWRIGHT_HTML_REPORT: playwrightHtml,
  PLAYWRIGHT_JSON_REPORT: playwrightJson,
};

const steps = [
  { name: "lint", cmd: "npm", args: ["run", "lint"] },
  { name: "typecheck", cmd: "npm", args: ["run", "typecheck"] },
  { name: "build", cmd: "npm", args: ["run", "build"] },
  { name: "e2e", cmd: "npm", args: ["run", "e2e"] },
];

const statusRows = [];
let failed = false;

for (const step of steps) {
  const code = runStep(step.name, step.cmd, step.args, commonEnv, repoRoot, reportDir);
  statusRows.push({ step: step.name, code });
  if (code !== 0) {
    failed = true;
    break;
  }
}

const summary = [
  "# Frontend Regression Gate",
  "",
  `- Timestamp: ${stamp}`,
  `- Frontend base: ${commonEnv.PLAYWRIGHT_BASE_URL}`,
  `- Backend base: ${commonEnv.E2E_BACKEND_URL}`,
  "",
  "## Status",
  "",
  "| Step | Exit Code |",
  "|---|---:|",
  ...statusRows.map((r) => `| ${r.step} | ${r.code} |`),
  "",
  "## Artifact Paths",
  "",
  `- Playwright HTML: \`${playwrightHtml}\``,
  `- Playwright JSON: \`${playwrightJson}\``,
  `- Playwright Output: \`${playwrightOutput}\``,
  "",
];

fs.writeFileSync(path.join(reportDir, "Summary.md"), summary.join("\n"), "utf-8");

console.log(`Regression gate report: ${reportDir}`);
process.exit(failed ? 1 : 0);

