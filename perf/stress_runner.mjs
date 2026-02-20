import fs from "node:fs";
import path from "node:path";
import autocannon from "autocannon";

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function runAutocannon(opts) {
  return new Promise((resolve, reject) => {
    autocannon(opts, (err, result) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(result);
    });
  });
}

function pct(v) {
  if (v == null) {
    return null;
  }
  return Number((v * 100).toFixed(4));
}

function p95FromLatency(latency) {
  if (!latency || typeof latency !== "object") {
    return null;
  }
  if (latency.p95 != null) {
    return latency.p95;
  }
  if (latency.p97_5 != null) {
    return latency.p97_5;
  }
  return latency.p90 ?? null;
}

function fmt(v, d = 2) {
  if (v == null || Number.isNaN(v)) {
    return "n/a";
  }
  return Number(v).toFixed(d);
}

function md(report) {
  const lines = [];
  lines.push("# Stress Test Report");
  lines.push("");
  lines.push(`Generated: ${report.generatedAt}`);
  lines.push(`Endpoint: ${report.endpoint.method} ${report.endpoint.path}`);
  lines.push(`Cliff policy: p95 > ${report.thresholds.maxP95Ms}ms OR error rate > ${report.thresholds.maxErrorRatePct}%`);
  lines.push(`Result: ${report.cliffDetected ? "CLIFF DETECTED" : "NO CLIFF DETECTED"}`);
  lines.push("");
  lines.push("| Concurrency | p95 (ms) | p99 (ms) | Avg RPS | Error % | Verdict |");
  lines.push("|---:|---:|---:|---:|---:|---|");
  for (const r of report.runs) {
    lines.push(
      `| ${r.concurrency} | ${fmt(r.p95)} | ${fmt(r.p99)} | ${fmt(r.rps)} | ${fmt(r.errorPct)} | ${r.verdict} |`,
    );
  }
  lines.push("");
  if (report.cliffAt) {
    lines.push(`Cliff at concurrency ${report.cliffAt.concurrency}: ${report.cliffAt.reason}.`);
  }
  return `${lines.join("\n")}\n`;
}

async function main() {
  const cfgPath = process.argv[2] || "perf/config.stress.json";
  const outJson = process.argv[3] || "reports/perf/stress.json";
  const outMd = process.argv[4] || "reports/perf/stress.md";
  const cfg = readJson(cfgPath);

  const baseUrl = process.env.PERF_BASE_URL || cfg.baseUrl;
  const endpoint = cfg.endpoint;
  const url = `${baseUrl.replace(/\/$/, "")}${endpoint.path}`;

  const thresholds = {
    maxP95Ms: Number(process.env.PERF_STRESS_MAX_P95_MS || cfg.thresholds.maxP95Ms || 1200),
    maxErrorRatePct: Number(process.env.PERF_STRESS_MAX_ERROR_RATE_PCT || cfg.thresholds.maxErrorRatePct || 2),
  };

  const runs = [];
  let cliffAt = null;

  for (const c of cfg.concurrencyRamp) {
    const res = await runAutocannon({
      url,
      method: endpoint.method || "GET",
      connections: c,
      duration: Number(cfg.durationSec || 30),
      timeout: Number(cfg.timeoutSec || 20),
      headers: endpoint.headers || {},
      body: endpoint.body ? JSON.stringify(endpoint.body) : undefined,
    });

    const total = res?.requests?.total || 0;
    const fail = (res?.errors || 0) + (res?.timeouts || 0) + (res?.non2xx || 0);
    const denom = total + fail;
    const errorRate = denom > 0 ? Math.min(1, fail / denom) : null;

    const row = {
      concurrency: c,
      p95: p95FromLatency(res?.latency),
      p99: res?.latency?.p99 ?? null,
      rps: res?.requests?.average ?? null,
      errorPct: errorRate == null ? null : pct(errorRate),
      verdict: "ok",
    };

    if (row.p95 != null && row.p95 > thresholds.maxP95Ms) {
      row.verdict = "cliff";
      cliffAt = cliffAt || { concurrency: c, reason: `p95 ${fmt(row.p95)}ms > ${thresholds.maxP95Ms}ms` };
    }
    if (row.errorPct != null && row.errorPct > thresholds.maxErrorRatePct) {
      row.verdict = "cliff";
      cliffAt = cliffAt || { concurrency: c, reason: `error ${fmt(row.errorPct)}% > ${thresholds.maxErrorRatePct}%` };
    }

    runs.push(row);

    if (cliffAt && cfg.stopOnCliff !== false) {
      break;
    }
  }

  const report = {
    generatedAt: new Date().toISOString(),
    endpoint,
    durationSec: Number(cfg.durationSec || 30),
    timeoutSec: Number(cfg.timeoutSec || 20),
    thresholds,
    runs,
    cliffDetected: Boolean(cliffAt),
    cliffAt,
  };

  ensureDir(outJson);
  ensureDir(outMd);
  fs.writeFileSync(outJson, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(outMd, md(report), "utf8");
  console.log(`[perf] wrote ${outJson}`);
  console.log(`[perf] wrote ${outMd}`);
}

main().catch((err) => {
  console.error("[perf] stress runner failed:", err.message);
  process.exit(1);
});
