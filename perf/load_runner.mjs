import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import autocannon from "autocannon";

function nowIso() {
  return new Date().toISOString();
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function percentile(obj, key, fallback = null) {
  if (!obj || typeof obj !== "object") {
    return fallback;
  }
  return Object.prototype.hasOwnProperty.call(obj, key) ? obj[key] : fallback;
}

function quantile(obj, target) {
  if (!obj || typeof obj !== "object") {
    return null;
  }
  if (target === "p95") {
    return percentile(obj, "p95", percentile(obj, "p97_5", percentile(obj, "p90", null)));
  }
  return percentile(obj, target, null);
}

function captureDockerStats(containerName) {
  if (!containerName) {
    return null;
  }
  try {
    const raw = execSync(
      `docker stats ${containerName} --no-stream --format "{{json .}}"`,
      { stdio: ["ignore", "pipe", "ignore"] },
    )
      .toString()
      .trim();
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function parseMemoryToBytes(raw) {
  if (!raw || typeof raw !== "string") {
    return null;
  }
  const m = raw.trim().match(/^([\d.]+)\s*([KMGTP]i?)?B?$/i);
  if (!m) {
    return null;
  }
  const value = Number(m[1]);
  const unit = (m[2] || "").toUpperCase();
  const factors = {
    "": 1,
    K: 1000,
    M: 1000 ** 2,
    G: 1000 ** 3,
    T: 1000 ** 4,
    KI: 1024,
    MI: 1024 ** 2,
    GI: 1024 ** 3,
    TI: 1024 ** 4,
  };
  return Number.isFinite(value) ? value * (factors[unit] || 1) : null;
}

function parseDockerSample(sample) {
  if (!sample) {
    return null;
  }
  const cpuPct = sample.CPUPerc ? Number(String(sample.CPUPerc).replace("%", "")) : null;
  const memUsage = sample.MemUsage ? String(sample.MemUsage).split("/")[0].trim() : null;
  return {
    at: nowIso(),
    cpuPct: Number.isFinite(cpuPct) ? cpuPct : null,
    memBytes: parseMemoryToBytes(memUsage),
    raw: sample,
  };
}

function summarizeResourceSamples(samples) {
  const cpu = samples.map((x) => x.cpuPct).filter((x) => x != null);
  const mem = samples.map((x) => x.memBytes).filter((x) => x != null);
  const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);
  const max = (arr) => (arr.length ? Math.max(...arr) : null);
  return {
    sampleCount: samples.length,
    avgCpuPct: avg(cpu),
    maxCpuPct: max(cpu),
    avgMemBytes: avg(mem),
    maxMemBytes: max(mem),
    samples,
  };
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

function resolveHeaders(endpoint) {
  const headers = { ...(endpoint.headers || {}) };
  const fromEnv = endpoint.headersFromEnv || {};
  for (const [headerName, envName] of Object.entries(fromEnv)) {
    const value = process.env[envName];
    if (value) {
      headers[headerName] = value;
    }
  }
  return headers;
}

function resolveBody(endpoint) {
  if (typeof endpoint.body === "string") {
    return endpoint.body;
  }
  if (endpoint.body && typeof endpoint.body === "object") {
    return JSON.stringify(endpoint.body);
  }
  if (endpoint.bodyFromEnvJson) {
    const raw = process.env[endpoint.bodyFromEnvJson];
    if (!raw) {
      return undefined;
    }
    try {
      return JSON.stringify(JSON.parse(raw));
    } catch {
      return raw;
    }
  }
  return undefined;
}

function missingRequiredEnv(requiredEnv) {
  const missing = [];
  for (const name of requiredEnv || []) {
    if (!process.env[name]) {
      missing.push(name);
    }
  }
  return missing;
}

function toSummary(result, testMeta) {
  const totalRequests = result?.requests?.total ?? 0;
  const errors = result?.errors ?? 0;
  const timeouts = result?.timeouts ?? 0;
  const non2xx = result?.non2xx ?? 0;
  const failureCount = errors + timeouts + non2xx;
  const denominator = totalRequests + failureCount;

  return {
    endpoint: testMeta.endpoint,
    method: testMeta.method,
    path: testMeta.path,
    url: testMeta.url,
    concurrency: testMeta.concurrency,
    durationSec: testMeta.durationSec,
    startedAt: testMeta.startedAt,
    finishedAt: testMeta.finishedAt,
    requests: {
      total: totalRequests,
      averageRps: result?.requests?.average ?? null,
      minRps: result?.requests?.min ?? null,
      maxRps: result?.requests?.max ?? null,
      p50Rps: quantile(result?.requests, "p50"),
      p95Rps: quantile(result?.requests, "p95"),
      p99Rps: quantile(result?.requests, "p99"),
    },
    latencyMs: {
      average: result?.latency?.average ?? null,
      min: result?.latency?.min ?? null,
      max: result?.latency?.max ?? null,
      p50: quantile(result?.latency, "p50"),
      p95: quantile(result?.latency, "p95"),
      p99: quantile(result?.latency, "p99"),
    },
    throughputBytes: {
      average: result?.throughput?.average ?? null,
      min: result?.throughput?.min ?? null,
      max: result?.throughput?.max ?? null,
    },
    failures: {
      errors,
      timeouts,
      non2xx,
      failureCount,
      errorRate: denominator > 0 ? Math.min(1, failureCount / denominator) : 0,
    },
    statusCodes: result?.statusCodeStats ?? null,
    dockerStats: testMeta.dockerStats ?? null,
  };
}

function printRun(summary) {
  const p95 = summary.latencyMs.p95 ?? "n/a";
  const p99 = summary.latencyMs.p99 ?? "n/a";
  const rps = summary.requests.averageRps ?? "n/a";
  const err = summary.failures.errorRate == null ? "n/a" : (summary.failures.errorRate * 100).toFixed(2);
  console.log(
    `[perf] ${summary.endpoint} c=${summary.concurrency} p95=${p95}ms p99=${p99}ms rps=${rps} err=${err}%`,
  );
}

async function runEndpointCase({ endpoint, concurrency, cfg, baseUrl, dockerContainer }) {
  const url = `${baseUrl.replace(/\/$/, "")}${endpoint.path}`;
  const startedAt = nowIso();
  const resourceSamples = [];
  let sampler = null;
  if (dockerContainer) {
    sampler = setInterval(() => {
      const s = parseDockerSample(captureDockerStats(dockerContainer));
      if (s) {
        resourceSamples.push(s);
      }
    }, 1000);
  }

  const method = endpoint.method || "GET";
  const headers = resolveHeaders(endpoint);
  const body = resolveBody(endpoint);

  if (body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const result = await runAutocannon({
    url,
    method,
    headers,
    body,
    connections: concurrency,
    duration: Number(endpoint.durationSec || cfg.durationSec),
    timeout: Number(endpoint.timeoutSec || cfg.timeoutSec),
    amount: endpoint.amount,
    pipelining: endpoint.pipelining,
  });

  if (sampler) {
    clearInterval(sampler);
  }

  const finishedAt = nowIso();
  const summary = toSummary(result, {
    endpoint: endpoint.name,
    method,
    path: endpoint.path,
    url,
    concurrency,
    durationSec: Number(endpoint.durationSec || cfg.durationSec),
    startedAt,
    finishedAt,
    dockerStats: summarizeResourceSamples(resourceSamples),
  });
  return summary;
}

async function runSuite(configPath, outPath) {
  const cfg = readJson(configPath);
  const baseUrl = process.env.PERF_BASE_URL || cfg.baseUrl;
  const dockerContainer = process.env.PERF_DOCKER_CONTAINER || cfg.dockerContainer || null;

  const runs = [];
  const skipped = [];

  for (const endpoint of cfg.endpoints || []) {
    const missing = missingRequiredEnv(endpoint.requiredEnv || []);
    if (missing.length) {
      skipped.push({
        endpoint: endpoint.name,
        path: endpoint.path,
        reason: `Missing required env: ${missing.join(", ")}`,
      });
      console.log(`[perf] skip ${endpoint.name}: missing env ${missing.join(", ")}`);
      continue;
    }

    for (const concurrency of cfg.concurrencyLadder || [1]) {
      const summary = await runEndpointCase({ endpoint, concurrency, cfg, baseUrl, dockerContainer });
      runs.push(summary);
      printRun(summary);
    }
  }

  const payload = {
    suite: cfg.name,
    generatedAt: nowIso(),
    baseUrl,
    configPath,
    durationSec: cfg.durationSec,
    timeoutSec: cfg.timeoutSec,
    concurrencyLadder: cfg.concurrencyLadder,
    endpointCount: (cfg.endpoints || []).length,
    runs,
    skipped,
    metadata: cfg.metadata || {},
  };

  ensureDir(outPath);
  fs.writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(`[perf] wrote ${outPath}`);
}

const configPath = process.argv[2];
const outPath = process.argv[3];

if (!configPath || !outPath) {
  console.error("Usage: node perf/load_runner.mjs <config.json> <out.json>");
  process.exit(1);
}

runSuite(configPath, outPath).catch((err) => {
  console.error("[perf] load runner failed:", err.message);
  process.exit(1);
});
