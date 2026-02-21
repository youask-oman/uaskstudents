import readline from "node:readline";
import { performance } from "node:perf_hooks";
import "@mathjax/src/bundle/require.mjs";
import { mathjax } from "@mathjax/src/mjs/mathjax.js";
import { TeX } from "@mathjax/src/mjs/input/tex.js";
import { SVG } from "@mathjax/src/mjs/output/svg.js";
import { liteAdaptor } from "@mathjax/src/mjs/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "@mathjax/src/mjs/handlers/html.js";
import { handleRetriesFor } from "@mathjax/src/mjs/util/Retries.js";
import "@mathjax/src/mjs/util/asyncLoad/node.js";
import "@mathjax/src/mjs/input/tex/base/BaseConfiguration.js";
import "@mathjax/src/mjs/input/tex/ams/AmsConfiguration.js";
import "@mathjax/src/mjs/input/tex/newcommand/NewcommandConfiguration.js";
import "@mathjax/src/mjs/input/tex/noundefined/NoUndefinedConfiguration.js";
import { MathJaxNewcmFont } from "@mathjax/mathjax-newcm-font/mjs/svg.js";
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
const svg = new SVG({
  fontCache: "none",
  fontData: MathJaxNewcmFont,
  dynamicPrefix: "@mathjax/mathjax-newcm-font/mjs/svg/dynamic",
});
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

function toStandaloneSvg(node) {
  if (!node) return "";
  const kind = String(adaptor.kind(node) || "").toLowerCase();
  if (kind === "svg") {
    return adaptor.outerHTML(node);
  }
  const first = adaptor.firstChild(node);
  if (first && String(adaptor.kind(first) || "").toLowerCase() === "svg") {
    return adaptor.outerHTML(first);
  }
  return adaptor.outerHTML(node);
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

function ensureMathWrapped(latex, displayMode) {
  const src = String(latex || "").trim();
  if (!src) return src;
  let inner = src;
  if (inner.startsWith("\\(") && inner.endsWith("\\)")) {
    inner = inner.slice(2, -2).trim();
  } else if (inner.startsWith("\\[") && inner.endsWith("\\]")) {
    inner = inner.slice(2, -2).trim();
  } else if (inner.startsWith("$$") && inner.endsWith("$$")) {
    inner = inner.slice(2, -2).trim();
  } else if (inner.startsWith("$") && inner.endsWith("$")) {
    inner = inner.slice(1, -1).trim();
  }
  if (!inner) return inner;
  return displayMode ? `\\displaystyle{${inner}}` : `{${inner}}`;
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
  const latexForMathJax = ensureMathWrapped(latex, displayMode);

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
      document.convertPromise(latexForMathJax, {
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
    let svgText = toStandaloneSvg(node);
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
