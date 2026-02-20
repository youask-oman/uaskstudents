import fs from "node:fs";
import path from "node:path";

function bytesFromFiles(files) {
  let total = 0;
  const details = [];
  for (const rel of files) {
    const abs = path.join(".next", rel);
    if (!fs.existsSync(abs)) {
      continue;
    }
    const size = fs.statSync(abs).size;
    total += size;
    details.push({ file: rel, sizeBytes: size });
  }
  return { total, details };
}

function formatMiB(bytes) {
  return (bytes / (1024 * 1024)).toFixed(3);
}

const manifestPath = ".next/build-manifest.json";
if (!fs.existsSync(manifestPath)) {
  console.error("Missing .next/build-manifest.json. Run `npm run build` first.");
  process.exit(1);
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const firstLoadFiles = [
  ...(manifest.polyfillFiles || []),
  ...(manifest.rootMainFiles || []),
];
const allChunkFiles = [
  ...(manifest.polyfillFiles || []),
  ...(manifest.rootMainFiles || []),
  ...(manifest.lowPriorityFiles || []),
];

const first = bytesFromFiles(firstLoadFiles);
const all = bytesFromFiles(allChunkFiles);
const routeSizes = Object.entries(manifest.pages || {})
  .map(([route, files]) => {
    const { total } = bytesFromFiles(files || []);
    return { route, totalBytes: total };
  })
  .sort((a, b) => b.totalBytes - a.totalBytes);

const firstLoadBudgetBytes = Number(process.env.PERF_FIRST_LOAD_BUDGET_BYTES || 800000);
const chunkBudgetBytes = Number(process.env.PERF_TOTAL_CHUNKS_BUDGET_BYTES || 3000000);
const routeBudgetBytes = Number(process.env.PERF_MAX_ROUTE_BUNDLE_BYTES || 1200000);
const routeBudgetViolations = routeSizes.filter((r) => r.totalBytes > routeBudgetBytes);

const report = {
  generatedAt: new Date().toISOString(),
  firstLoad: {
    files: first.details,
    totalBytes: first.total,
    budgetBytes: firstLoadBudgetBytes,
    withinBudget: first.total <= firstLoadBudgetBytes,
  },
  totalChunks: {
    files: all.details,
    totalBytes: all.total,
    budgetBytes: chunkBudgetBytes,
    withinBudget: all.total <= chunkBudgetBytes,
  },
  routes: {
    budgetBytes: routeBudgetBytes,
    topRoutes: routeSizes.slice(0, 20),
    violations: routeBudgetViolations,
    withinBudget: routeBudgetViolations.length === 0,
  },
};

fs.mkdirSync("reports", { recursive: true });
fs.writeFileSync("reports/perf_bundle_budget.json", `${JSON.stringify(report, null, 2)}\n`, "utf8");

console.log(
  `[perf-bundle] first-load=${formatMiB(first.total)}MiB budget=${formatMiB(firstLoadBudgetBytes)}MiB`,
);
console.log(
  `[perf-bundle] total-chunks=${formatMiB(all.total)}MiB budget=${formatMiB(chunkBudgetBytes)}MiB`,
);

if (!report.firstLoad.withinBudget || !report.totalChunks.withinBudget) {
  console.error("[perf-bundle] Budget exceeded.");
  process.exit(1);
}

if (!report.routes.withinBudget) {
  console.error(
    `[perf-bundle] Route budget exceeded for ${report.routes.violations.length} routes (budget=${formatMiB(routeBudgetBytes)}MiB).`,
  );
  console.error("[perf-bundle] Budget exceeded.");
  process.exit(1);
}
