import { execSync } from "node:child_process";
import fs from "node:fs";

function run(cmd) {
  execSync(cmd, { stdio: "inherit" });
}

function readJson(path) {
  return JSON.parse(fs.readFileSync(path, "utf8"));
}

function writeBaselineMarkdown(baselineJsonPath) {
  const baseline = readJson(baselineJsonPath);
  const lines = [];
  lines.push("# Performance Baseline");
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Suite: ${baseline.suite}`);
  lines.push(`Base URL: ${baseline.baseUrl}`);
  lines.push("");
  lines.push("## Critical Flows");
  lines.push("- Solve endpoints: /api/v1/solve, /api/v1/solve/batch (configured as optional; require auth/payload env)");
  lines.push("- Auth/session endpoints: /api/v1/login and /api/v1/history (optional; require auth env)");
  lines.push("- History/profile endpoints: /api/v1/history, /api/v1/user/profile (optional; require auth env)");
  lines.push("- Upload/import endpoints: /api/v1/uploads, /api/v1/import (optional; require multipart/auth env)");
  lines.push("");
  lines.push("## Smoke Results");
  lines.push("| Endpoint | Concurrency | p50 (ms) | p95 (ms) | p99 (ms) | Avg RPS | Error % | Avg CPU % | Max Mem (MiB) |");
  lines.push("|---|---:|---:|---:|---:|---:|---:|---:|---:|");
  for (const runItem of baseline.runs || []) {
    const err = runItem.failures?.errorRate == null ? "n/a" : (runItem.failures.errorRate * 100).toFixed(2);
    const avgCpu = runItem.dockerStats?.avgCpuPct == null ? "n/a" : Number(runItem.dockerStats.avgCpuPct).toFixed(2);
    const maxMemMiB = runItem.dockerStats?.maxMemBytes == null ? "n/a" : (runItem.dockerStats.maxMemBytes / (1024 * 1024)).toFixed(2);
    lines.push(
      `| ${runItem.endpoint} | ${runItem.concurrency} | ${runItem.latencyMs?.p50 ?? "n/a"} | ${runItem.latencyMs?.p95 ?? "n/a"} | ${runItem.latencyMs?.p99 ?? "n/a"} | ${runItem.requests?.averageRps ?? "n/a"} | ${err} | ${avgCpu} | ${maxMemMiB} |`,
    );
  }
  lines.push("");
  if ((baseline.skipped || []).length) {
    lines.push("## Skipped Endpoints");
    for (const s of baseline.skipped) {
      lines.push(`- ${s.endpoint}: ${s.reason}`);
    }
    lines.push("");
  }
  lines.push("## Notes");
  lines.push("- Baseline artifact is persisted at perf/perf_baseline.json.");
  lines.push("- CI gate compares current run against this baseline with threshold checks.");

  fs.writeFileSync("reports/perf_baseline.md", `${lines.join("\n")}\n`, "utf8");
}

fs.mkdirSync("reports/perf", { recursive: true });
fs.mkdirSync("perf", { recursive: true });

const baselineArtifact = "perf/perf_baseline.json";
const currentOut = "reports/perf/perf_current.json";

run(`node perf/load_runner.mjs perf/config.smoke.json ${currentOut}`);

if (!fs.existsSync(baselineArtifact)) {
  fs.copyFileSync(currentOut, baselineArtifact);
  console.log(`[perf] baseline seeded at ${baselineArtifact}`);
}

run(
  `node perf/compare_results.mjs ${baselineArtifact} ${currentOut} reports/perf_regression.md reports/perf/perf_regression.json true`,
);

if (!fs.existsSync(".next/build-manifest.json")) {
  run("npm run build");
}
run("node perf/check_bundle_budget.mjs");

writeBaselineMarkdown(baselineArtifact);
console.log("[perf] wrote reports/perf_baseline.md");