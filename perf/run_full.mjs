import { execSync } from "node:child_process";
import fs from "node:fs";

function run(cmd) {
  execSync(cmd, { stdio: "inherit" });
}

fs.mkdirSync("reports/perf", { recursive: true });
fs.mkdirSync("profiles", { recursive: true });

run("node perf/load_runner.mjs perf/config.full.json reports/perf/full_run.json");
run("node perf/stress_runner.mjs perf/config.stress.json reports/perf/stress.json reports/perf/stress.md");
run("node perf/soak_runner.mjs perf/config.soak.json reports/perf/soak.json reports/perf/soak.md");
run("python perf/db_checks.py");
run("node perf/generate_db_report.mjs reports/perf_db_checks.json reports/db_perf.md");
run("node perf/generate_runtime_safety_report.mjs");
run("node perf/generate_container_sanity_report.mjs");

if (!fs.existsSync(".next/build-manifest.json")) {
  run("npm run build");
}
run("node perf/check_bundle_budget.mjs");

console.log("[perf] full suite complete");