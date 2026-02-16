import readline from "node:readline";
import { performance } from "node:perf_hooks";
import { mathjax } from "@mathjax/src/js/mathjax.js";
import { TeX } from "@mathjax/src/js/input/tex.js";
import { SVG } from "@mathjax/src/js/output/svg.js";
import { liteAdaptor } from "@mathjax/src/js/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "@mathjax/src/js/handlers/html.js";
import { handleRetriesFor } from "@mathjax/src/js/util/Retries.js";
import "@mathjax/src/js/input/tex/base/BaseConfiguration.js";
import "@mathjax/src/js/input/tex/ams/AmsConfiguration.js";
import "@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js";
import "@mathjax/src/js/input/tex/noundefined/NoUndefinedConfiguration.js";
import { sanitizeSvg } from "./sanitize_svg.js";

global.MathJax = {
  loader: {
    paths: {
      mathjax: "@mathjax/src/bundle",
    },
  },
};

const MAX_MACROS = 25;
const MAX_MACRO_TEXT_BYTES = 2048;
// 1s is often too tight in real deployments and causes fallback text rendering.
const DEFAULT_TIMEOUT_MS = Number(process.env.MATHJAX_ITEM_TIMEOUT_MS || "5000");

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);

const tex = new TeX({
  packages: ["base", "ams", "newcommand", "noundefined"],
});
const svg = new SVG({ fontCache: "none" });
const document = mathjax.document("", { InputJax: tex, OutputJax: svg });

function parseSizeAttr(svgText, attr) {
  const m = svgText.match(new RegExp(`${attr}="([^"]+)"`));
  if (!m) return null;
  const raw = (m[1] || "").trim();
  const num = Number.parseFloat(raw.replace(/ex|em|px|pt|cm|mm|in/g, ""));
  return Number.isFinite(num) ? num : null;
}

function extractMetrics(svgText) {
  const viewBox = /viewBox="([^"]+)"/.exec(svgText)?.[1] || "";
  const parts = viewBox.split(/\s+/).map((x) => Number.parseFloat(x)).filter((x) => Number.isFinite(x));
  const width = parseSizeAttr(svgText, "width") ?? (parts.length === 4 ? parts[2] : null);
  const height = parseSizeAttr(svgText, "height") ?? (parts.length === 4 ? parts[3] : null);
  return { width, height, baseline: null };
}

function macroSizeOk(macros) {
  if (!macros || typeof macros !== "object") return { ok: true };
  const entries = Object.entries(macros);
  if (entries.length > MAX_MACROS) {
    return { ok: false, code: "MACRO_LIMIT", message: `Too many macros (${entries.length} > ${MAX_MACROS})` };
  }
  const bytes = Buffer.byteLength(JSON.stringify(macros), "utf8");
  if (bytes > MAX_MACRO_TEXT_BYTES) {
    return { ok: false, code: "MACRO_LIMIT", message: `Macros too large (${bytes} bytes > ${MAX_MACRO_TEXT_BYTES})` };
  }
  return { ok: true };
}

async function renderOne(req) {
  const started = performance.now();
  const id = String(req?.id || "");
  const latex = String(req?.latex || "");
  const displayMode = Boolean(req?.display_mode);
  const scale = Number(req?.scale ?? 1.0);
  const sanitize = req?.sanitize !== false;
  const timeoutMs = Number(req?.timeout_ms || DEFAULT_TIMEOUT_MS);
  const macros = req?.macros || {};

  const macroCheck = macroSizeOk(macros);
  if (!macroCheck.ok) {
    return {
      id,
      ok: false,
      error: { code: macroCheck.code, message: macroCheck.message },
      fallback_text: latex,
      metrics: { duration_ms: Math.round(performance.now() - started) },
    };
  }

  try {
    const convertPromise = handleRetriesFor(() =>
      document.convertPromise(latex, {
        display: displayMode,
        scale: Number.isFinite(scale) ? scale : 1.0,
        em: 16,
        ex: 8,
        containerWidth: 80 * 16,
      })
    );
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error("render-timeout")), timeoutMs);
    });
    const node = await Promise.race([convertPromise, timeoutPromise]);
    let svgText = adaptor.outerHTML(node);
    if (sanitize) {
      svgText = sanitizeSvg(svgText);
    }
    const metrics = extractMetrics(svgText);
    metrics.duration_ms = Math.round(performance.now() - started);
    return { id, ok: true, svg: svgText, metrics };
  } catch (err) {
    const message = String(err?.message || err || "Render failed");
    let code = "TEX_PARSE_ERROR";
    if (message.includes("timeout")) {
      code = "TIMEOUT";
    }
    return {
      id,
      ok: false,
      error: { code, message },
      fallback_text: latex,
      metrics: { duration_ms: Math.round(performance.now() - started) },
    };
  }
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", async (line) => {
  let parsed = null;
  try {
    parsed = JSON.parse(line);
  } catch {
    process.stdout.write(
      JSON.stringify({
        id: null,
        ok: false,
        error: { code: "BAD_JSON", message: "Invalid JSONL request" },
        fallback_text: "",
      }) + "\n"
    );
    return;
  }
  const result = await renderOne(parsed);
  process.stdout.write(JSON.stringify(result) + "\n");
});
