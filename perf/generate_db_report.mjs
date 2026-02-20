import fs from "node:fs";

function fmt(v, d = 2) {
  if (v == null || Number.isNaN(v)) {
    return "n/a";
  }
  return Number(v).toFixed(d);
}

const inPath = process.argv[2] || "reports/perf_db_checks.json";
const outPath = process.argv[3] || "reports/db_perf.md";

if (!fs.existsSync(inPath)) {
  console.error(`[perf-db] missing ${inPath}`);
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inPath, "utf8"));
const lines = [];
lines.push("# DB Performance Report");
lines.push("");
lines.push(`Generated: ${data.generatedAt || new Date().toISOString()}`);
lines.push(`pg_stat_statements enabled: ${data.pgStatStatementsAvailable ? "yes" : "no"}`);
lines.push("");

if (data.topSlowQueries?.length) {
  lines.push("## Top Slow Queries");
  lines.push("| Query ID | Calls | Total Exec (ms) | Mean Exec (ms) |");
  lines.push("|---|---:|---:|---:|");
  for (const q of data.topSlowQueries) {
    lines.push(`| ${q.queryid} | ${q.calls} | ${fmt(q.totalExecMs)} | ${fmt(q.meanExecMs)} |`);
  }
  lines.push("");
}

if (data.explainAnalyze?.length) {
  lines.push("## EXPLAIN ANALYZE Summary");
  for (const ex of data.explainAnalyze) {
    lines.push(`- ${ex.queryid}: ${ex.status}`);
    if (ex.status === "failed" && ex.error) {
      lines.push(`  - error: ${ex.error}`);
    }
  }
  lines.push("");
}

if (data.nPlusOneHeuristics?.length) {
  lines.push("## N+1 Heuristics");
  for (const h of data.nPlusOneHeuristics) {
    lines.push(`- ${h.queryid}: calls=${h.calls}, mean=${fmt(h.meanExecMs)}ms, reason=${h.reason}`);
  }
  lines.push("");
}

lines.push("## Notes");
if (data.notes?.length) {
  for (const n of data.notes) {
    lines.push(`- ${n}`);
  }
} else {
  lines.push("- No additional notes.");
}

fs.mkdirSync("reports", { recursive: true });
fs.writeFileSync(outPath, `${lines.join("\n")}\n`, "utf8");
console.log(`[perf-db] wrote ${outPath}`);