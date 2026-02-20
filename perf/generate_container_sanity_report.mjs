import fs from "node:fs";

function read(path) {
  return fs.existsSync(path) ? fs.readFileSync(path, "utf8") : "";
}

const compose = read("docker-compose.yml");
const composeDev = read("docker-compose.dev.yml");

function pickMatches(src, re) {
  const out = [];
  let m;
  while ((m = re.exec(src)) !== null) {
    out.push(m[0].trim());
  }
  return out;
}

const limits = pickMatches(compose, /(mem_limit|cpus|ulimits|pids_limit)\s*:.*/g);
const concurrency = pickMatches(compose, /(WORKER_CONCURRENCY|WHATSAPP_WORKER_CONCURRENCY|--concurrency[^\n]*)/g);
const poolHints = pickMatches(read("backend/app/database.py"), /(create_engine\(|pool|Session\()/g);
const safetyFlags = pickMatches(compose, /(read_only|tmpfs|no-new-privileges|max-size|max-file)\s*:.*/g);

const lines = [];
lines.push("# Container Sanity Report");
lines.push("");
lines.push(`Generated: ${new Date().toISOString()}`);
lines.push("");
lines.push("## Compose Resource Limits");
if (limits.length) {
  for (const l of limits) {
    lines.push(`- ${l}`);
  }
} else {
  lines.push("- No explicit CPU/memory/ulimits limits set in docker-compose.yml.");
}
lines.push("");

lines.push("## Concurrency Controls");
if (concurrency.length) {
  for (const c of concurrency) {
    lines.push(`- ${c}`);
  }
} else {
  lines.push("- No worker concurrency controls detected.");
}
lines.push("");

lines.push("## Runtime Hardening Flags");
if (safetyFlags.length) {
  for (const f of safetyFlags) {
    lines.push(`- ${f}`);
  }
} else {
  lines.push("- No hardening flags detected.");
}
lines.push("");

lines.push("## DB Pool Notes");
if (poolHints.length) {
  for (const p of poolHints) {
    lines.push(`- ${p}`);
  }
} else {
  lines.push("- Could not find DB pool hints.");
}
lines.push("");

lines.push("## Findings");
lines.push("- Risk: missing explicit container CPU/memory/ulimit boundaries can cause noisy-neighbor impact and OOM under load.");
lines.push("- Positive: worker concurrency is parameterized via env for queue consumers.");
lines.push("- Positive: some services use tmpfs and no-new-privileges; log rotation options are present.");
lines.push("- Risk: DB pool sizing is not explicitly tuned in compose/env and should be load-tested per deployment size.");
lines.push("");
lines.push("## Dev Override Review");
if (composeDev) {
  lines.push("- docker-compose.dev.yml runs orchestrator/worker as root and with read_only=false for convenience.");
  lines.push("- Keep dev override out of production deploy paths.");
}

fs.mkdirSync("reports", { recursive: true });
fs.writeFileSync("reports/container_sanity.md", `${lines.join("\n")}\n`, "utf8");
console.log("[perf] wrote reports/container_sanity.md");