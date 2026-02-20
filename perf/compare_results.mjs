import fs from "node:fs";
import path from "node:path";

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function keyOf(run) {
  return `${run.endpoint}|${run.method}|${run.path}|${run.concurrency}`;
}

function pctDelta(base, current) {
  if (base == null || current == null || base === 0) {
    return null;
  }
  return ((current - base) / base) * 100;
}

function fmt(n, digits = 2) {
  if (n == null || Number.isNaN(n)) {
    return "n/a";
  }
  return Number(n).toFixed(digits);
}

function loadIndex(filePath) {
  const data = readJson(filePath);
  const m = new Map();
  for (const run of data.runs || []) {
    m.set(keyOf(run), run);
  }
  return { data, map: m };
}

function evaluateRow(row, thresholds) {
  const violations = [];

  if (row.deltaP95 != null && row.deltaP95 > thresholds.maxP95RegressionPct) {
    violations.push(`p95 +${fmt(row.deltaP95)}% > +${fmt(thresholds.maxP95RegressionPct)}%`);
  }

  if (row.deltaRps != null && row.deltaRps < -Math.abs(thresholds.maxRpsDropPct)) {
    violations.push(`rps ${fmt(row.deltaRps)}% < -${fmt(Math.abs(thresholds.maxRpsDropPct))}%`);
  }

  if (row.baseErrPct != null && row.currErrPct != null && row.currErrPct > row.baseErrPct + thresholds.maxAbsoluteErrorRateIncreasePct) {
    violations.push(
      `error ${fmt(row.currErrPct)}% > ${fmt(row.baseErrPct + thresholds.maxAbsoluteErrorRateIncreasePct)}%`,
    );
  }

  return {
    pass: violations.length === 0,
    violations,
  };
}

function toMarkdown(meta) {
  const lines = [];
  lines.push("# Performance Regression Report");
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Baseline: ${meta.baselinePath}`);
  lines.push(`Current: ${meta.currentPath}`);
  lines.push("");
  lines.push("## Thresholds");
  lines.push(`- p95 latency regression: fail if > +${meta.thresholds.maxP95RegressionPct}%`);
  lines.push(`- RPS regression: fail if drop > ${Math.abs(meta.thresholds.maxRpsDropPct)}%`);
  lines.push(`- Error rate: fail on increase > ${meta.thresholds.maxAbsoluteErrorRateIncreasePct} absolute % points`);
  lines.push("");
  lines.push(`Overall gate: **${meta.pass ? "PASS" : "FAIL"}**`);
  lines.push("");
  lines.push("| Endpoint | C | p95 base | p95 curr | p95 d% | RPS base | RPS curr | RPS d% | Err base % | Err curr % | Gate | Violations | ");
  lines.push("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|");

  for (const r of meta.rows) {
    lines.push(
      `| ${r.endpoint} | ${r.concurrency} | ${fmt(r.baseP95)} | ${fmt(r.currP95)} | ${fmt(r.deltaP95)} | ${fmt(r.baseRps)} | ${fmt(r.currRps)} | ${fmt(r.deltaRps)} | ${fmt(r.baseErrPct)} | ${fmt(r.currErrPct)} | ${r.pass ? "PASS" : "FAIL"} | ${(r.violations || []).join("; ") || "-"} |`,
    );
  }

  lines.push("");
  if (meta.missingInCurrent.length) {
    lines.push("## Missing In Current");
    for (const miss of meta.missingInCurrent) {
      lines.push(`- ${miss}`);
    }
    lines.push("");
  }

  if (meta.baselineSkipped?.length || meta.currentSkipped?.length) {
    lines.push("## Skipped Endpoints");
    if (meta.baselineSkipped?.length) {
      lines.push("- Baseline:");
      for (const s of meta.baselineSkipped) {
        lines.push(`  - ${s.endpoint}: ${s.reason}`);
      }
    }
    if (meta.currentSkipped?.length) {
      lines.push("- Current:");
      for (const s of meta.currentSkipped) {
        lines.push(`  - ${s.endpoint}: ${s.reason}`);
      }
    }
    lines.push("");
  }

  return `${lines.join("\n")}\n`;
}

const baselinePath = process.argv[2];
const currentPath = process.argv[3];
const outMd = process.argv[4];
const outJson = process.argv[5];
const failOnRegression = String(process.argv[6] || "false").toLowerCase() === "true";

if (!baselinePath || !currentPath || !outMd || !outJson) {
  console.error("Usage: node perf/compare_results.mjs <baseline.json> <current.json> <out.md> <out.json> [failOnRegression]");
  process.exit(1);
}

const thresholds = {
  maxP95RegressionPct: Number(process.env.PERF_THRESHOLD_P95_REGRESSION_PCT || 15),
  maxRpsDropPct: Number(process.env.PERF_THRESHOLD_RPS_DROP_PCT || 10),
  maxAbsoluteErrorRateIncreasePct: Number(process.env.PERF_THRESHOLD_ERROR_RATE_INC_ABS_PCT || 0),
};

const base = loadIndex(baselinePath);
const curr = loadIndex(currentPath);
const rows = [];
const missingInCurrent = [];

for (const [k, b] of base.map.entries()) {
  const c = curr.map.get(k);
  if (!c) {
    missingInCurrent.push(k);
    continue;
  }
  const baseErrPct = b.failures?.errorRate == null ? null : b.failures.errorRate * 100;
  const currErrPct = c.failures?.errorRate == null ? null : c.failures.errorRate * 100;
  const row = {
    key: k,
    endpoint: b.endpoint,
    method: b.method,
    path: b.path,
    concurrency: b.concurrency,
    baseP95: b.latencyMs?.p95,
    currP95: c.latencyMs?.p95,
    deltaP95: pctDelta(b.latencyMs?.p95, c.latencyMs?.p95),
    baseP99: b.latencyMs?.p99,
    currP99: c.latencyMs?.p99,
    deltaP99: pctDelta(b.latencyMs?.p99, c.latencyMs?.p99),
    baseRps: b.requests?.averageRps,
    currRps: c.requests?.averageRps,
    deltaRps: pctDelta(b.requests?.averageRps, c.requests?.averageRps),
    baseErrPct,
    currErrPct,
    deltaErrPct: pctDelta(baseErrPct, currErrPct),
  };
  const gate = evaluateRow(row, thresholds);
  row.pass = gate.pass;
  row.violations = gate.violations;
  rows.push(row);
}

rows.sort((a, b) => (a.endpoint + a.concurrency).localeCompare(b.endpoint + b.concurrency));

const failures = rows.filter((r) => !r.pass);
const outPayload = {
  generatedAt: new Date().toISOString(),
  baselinePath,
  currentPath,
  thresholds,
  rowCount: rows.length,
  failCount: failures.length,
  pass: failures.length === 0 && missingInCurrent.length === 0,
  missingInCurrent,
  baselineSkipped: base.data.skipped || [],
  currentSkipped: curr.data.skipped || [],
  rows,
};

ensureDir(outMd);
ensureDir(outJson);
fs.writeFileSync(outMd, toMarkdown(outPayload), "utf8");
fs.writeFileSync(outJson, `${JSON.stringify(outPayload, null, 2)}\n`, "utf8");
console.log(`[perf] wrote ${outMd}`);
console.log(`[perf] wrote ${outJson}`);

if (failOnRegression && !outPayload.pass) {
  console.error(`[perf] regression gate failed: ${outPayload.failCount} failing rows, ${outPayload.missingInCurrent.length} missing rows.`);
  process.exit(2);
}