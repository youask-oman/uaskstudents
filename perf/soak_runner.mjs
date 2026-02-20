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

function fmt(v, d = 2) {
  if (v == null || Number.isNaN(v)) {
    return "n/a";
  }
  return Number(v).toFixed(d);
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

function md(report) {
  const lines = [];
  lines.push("# Soak Test Report");
  lines.push("");
  lines.push(`Generated: ${report.generatedAt}`);
  lines.push(`Endpoint: ${report.endpoint.method} ${report.endpoint.path}`);
  lines.push(`Total duration: ${report.totalDurationSec}s`);
  lines.push(`Window duration: ${report.windowDurationSec}s`);
  lines.push(`Connections: ${report.connections}`);
  lines.push("");
  lines.push("| Window | p95 (ms) | p99 (ms) | Avg RPS | Error % |");
  lines.push("|---:|---:|---:|---:|---:|");
  for (const w of report.windows) {
    lines.push(`| ${w.index} | ${fmt(w.p95)} | ${fmt(w.p99)} | ${fmt(w.rps)} | ${fmt(w.errorPct)} |`);
  }
  lines.push("");
  lines.push("## Drift");
  lines.push(`- p95 drift: ${fmt(report.drift.p95Pct)}%`);
  lines.push(`- error drift: ${fmt(report.drift.errorPctAbs)} percentage points`);
  lines.push(`- memory growth tracking: ${report.memoryTracking}`);
  return `${lines.join("\n")}\n`;
}

async function main() {
  const cfgPath = process.argv[2] || "perf/config.soak.json";
  const outJson = process.argv[3] || "reports/perf/soak.json";
  const outMd = process.argv[4] || "reports/perf/soak.md";
  const cfg = readJson(cfgPath);

  const baseUrl = process.env.PERF_BASE_URL || cfg.baseUrl;
  const endpoint = cfg.endpoint;
  const url = `${baseUrl.replace(/\/$/, "")}${endpoint.path}`;

  const totalDurationSec = Number(process.env.PERF_SOAK_DURATION_SEC || cfg.totalDurationSec || 1800);
  const windowDurationSec = Number(process.env.PERF_SOAK_WINDOW_SEC || cfg.windowDurationSec || 60);
  const connections = Number(process.env.PERF_SOAK_CONNECTIONS || cfg.connections || 20);
  const windowsCount = Math.max(1, Math.ceil(totalDurationSec / windowDurationSec));

  const windows = [];

  for (let i = 0; i < windowsCount; i += 1) {
    const runDuration = i === windowsCount - 1 ? Math.max(1, totalDurationSec - (i * windowDurationSec)) : windowDurationSec;
    const res = await runAutocannon({
      url,
      method: endpoint.method || "GET",
      connections,
      duration: runDuration,
      timeout: Number(cfg.timeoutSec || 20),
      headers: endpoint.headers || {},
      body: endpoint.body ? JSON.stringify(endpoint.body) : undefined,
    });

    const total = res?.requests?.total || 0;
    const fail = (res?.errors || 0) + (res?.timeouts || 0) + (res?.non2xx || 0);
    const denom = total + fail;
    const errorRate = denom > 0 ? (Math.min(1, fail / denom) * 100) : null;

    windows.push({
      index: i + 1,
      durationSec: runDuration,
      p95: p95FromLatency(res?.latency),
      p99: res?.latency?.p99 ?? null,
      rps: res?.requests?.average ?? null,
      errorPct: errorRate,
    });
  }

  const first = windows[0];
  const last = windows[windows.length - 1];
  const drift = {
    p95Pct: first?.p95 && last?.p95 ? ((last.p95 - first.p95) / first.p95) * 100 : null,
    errorPctAbs: first?.errorPct != null && last?.errorPct != null ? (last.errorPct - first.errorPct) : null,
  };

  const report = {
    generatedAt: new Date().toISOString(),
    endpoint,
    totalDurationSec,
    windowDurationSec,
    connections,
    windows,
    drift,
    memoryTracking: "Not directly measured in soak runner; use PERF_DOCKER_CONTAINER in load_runner outputs for memory sample trends.",
  };

  ensureDir(outJson);
  ensureDir(outMd);
  fs.writeFileSync(outJson, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  fs.writeFileSync(outMd, md(report), "utf8");
  console.log(`[perf] wrote ${outJson}`);
  console.log(`[perf] wrote ${outMd}`);
}

main().catch((err) => {
  console.error("[perf] soak runner failed:", err.message);
  process.exit(1);
});
