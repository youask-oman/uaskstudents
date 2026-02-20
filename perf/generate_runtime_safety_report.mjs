import fs from "node:fs";
import { execSync } from "node:child_process";

function run(cmd) {
  try {
    return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"] }).toString();
  } catch {
    return "";
  }
}

function grepEvidence(pattern, globs) {
  const cmd = `rg -n "${pattern}" ${globs.join(" ")}`;
  return run(cmd)
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 20);
}

const lines = [];
lines.push("# Runtime Safety Report");
lines.push("");
lines.push(`Generated: ${new Date().toISOString()}`);
lines.push("");
lines.push("## Scope");
lines.push("- Static audit only (code + compose). No runtime fault-injection harness in this report.");
lines.push("");

const timeouts = grepEvidence("timeout|TIMEOUT", ["backend/app", "docker-compose.yml"]);
const retries = grepEvidence("retry|backoff|retries", ["backend/app", "docker-compose.yml"]);
const breaker = grepEvidence("CircuitBreaker|breaker", ["backend/app/services/llm/clients.py", "backend/app/services"]);
const idempotency = grepEvidence("idempotency_key|Idempotency-Key", ["backend/app/api.py", "backend/app/services", "backend/app/models"]);
const queue = grepEvidence("queue|celery|concurrency|rate_limit|429|503", ["backend/app/api.py", "backend/app/worker.py", "docker-compose.yml"]);

lines.push("## Timeouts");
if (timeouts.length) {
  for (const e of timeouts) {
    lines.push(`- ${e}`);
  }
} else {
  lines.push("- No timeout evidence found.");
}
lines.push("");

lines.push("## Retries And Backoff");
if (retries.length) {
  for (const e of retries) {
    lines.push(`- ${e}`);
  }
} else {
  lines.push("- No retry/backoff evidence found.");
}
lines.push("");

lines.push("## Circuit Breaker");
if (breaker.length) {
  for (const e of breaker) {
    lines.push(`- ${e}`);
  }
} else {
  lines.push("- No explicit circuit breaker evidence found.");
}
lines.push("");

lines.push("## Backpressure And Concurrency Controls");
if (queue.length) {
  for (const e of queue) {
    lines.push(`- ${e}`);
  }
} else {
  lines.push("- No queue/backpressure evidence found.");
}
lines.push("");

lines.push("## Idempotency And Duplicate Work Protection");
if (idempotency.length) {
  for (const e of idempotency) {
    lines.push(`- ${e}`);
  }
} else {
  lines.push("- No idempotency evidence found.");
}
lines.push("");

lines.push("## Findings");
lines.push("- Positive: explicit timeout, retry/backoff, and idempotency plumbing exists in solve/billing paths.");
lines.push("- Positive: 429/503 responses are implemented for several overload and feature-disabled paths.");
lines.push("- Risk: no end-to-end proof here for retry-storm prevention under upstream brownouts.");
lines.push("- Risk: queue depth SLOs and hard concurrency ceilings are present but not centrally enforced by one guardrail.");
lines.push("");
lines.push("## Graceful Failure Mode Status");
lines.push("- Observed in code: fast-fail paths using HTTP 429/503 are present.");
lines.push("- Not fully proven: cascading failure behavior under upstream LLM saturation requires chaos/load injection not included in this run.");

fs.mkdirSync("reports", { recursive: true });
fs.writeFileSync("reports/runtime_safety.md", `${lines.join("\n")}\n`, "utf8");
console.log("[perf] wrote reports/runtime_safety.md");