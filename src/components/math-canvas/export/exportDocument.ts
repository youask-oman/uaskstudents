
import katex from "katex";
import type { ExportSolutionPayload } from "@/lib/export/docx/validate";
import type { CanvasPageData, StepRow } from "../types";

export interface SolutionExportPayload {
  pages: CanvasPageData[];
  title?: string;
  solveId?: string;
  tier?: string;
  generatedAt?: string;
}

const MATH_DELIMITER_RE = /(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g;
const HAS_DELIMITED_MATH_RE = /(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/;
const HAS_RAW_LATEX_RE = /\\[a-zA-Z]+|[_^{}]/;
const SAFE_PROTOCOL_RE = /^(https?:|mailto:)/i;

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const normalizeWhitespace = (value: string): string => value.replace(/\s+/g, " ").trim();
const decodeHtmlEntities = (value: string): string => {
  const source = String(value || "");
  if (!source) return "";
  if (typeof window !== "undefined" && typeof window.DOMParser !== "undefined") {
    const parser = new window.DOMParser();
    const parsed = parser.parseFromString(`<!doctype html><body>${source}`, "text/html");
    return parsed.body.textContent || source;
  }
  return source
    .replace(/&#x([0-9a-f]+);/gi, (_m, hex: string) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_m, dec: string) => String.fromCodePoint(Number.parseInt(dec, 10)))
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'");
};

const stripMathDelimiters = (value: string): string => {
  const trimmed = decodeHtmlEntities(value).trim();
  if (trimmed.startsWith("\\(") && trimmed.endsWith("\\)")) return trimmed.slice(2, -2).trim();
  if (trimmed.startsWith("\\[") && trimmed.endsWith("\\]")) return trimmed.slice(2, -2).trim();
  return trimmed;
};

const latexToHtml = (latex: string, displayMode: boolean): string => {
  const source = stripMathDelimiters(latex);
  if (!source) return "";
  try {
    return katex.renderToString(source, {
      throwOnError: false,
      displayMode,
      output: "mathml",
      strict: "ignore",
      trust: false,
    });
  } catch {
    return `<code>${escapeHtml(source)}</code>`;
  }
};

const proseWithMathToHtml = (value: string): string => {
  const text = value || "";
  if (!text) return "";
  let output = "";
  let cursor = 0;
  for (const match of text.matchAll(MATH_DELIMITER_RE)) {
    const index = match.index ?? -1;
    if (index < 0) continue;
    const full = match[0];
    const before = text.slice(cursor, index);
    output += escapeHtml(before).replace(/\n/g, "<br/>");
    const isDisplay = full.startsWith("\\[");
    output += latexToHtml(full, isDisplay);
    cursor = index + full.length;
  }
  output += escapeHtml(text.slice(cursor)).replace(/\n/g, "<br/>");
  return output;
};

const richMathToHtml = (value: string, displayMode = false): string => {
  const text = (value || "").trim();
  if (!text) return "";
  if (HAS_DELIMITED_MATH_RE.test(text)) return proseWithMathToHtml(text);
  if (HAS_RAW_LATEX_RE.test(text)) return latexToHtml(text, displayMode);
  return escapeHtml(text).replace(/\n/g, "<br/>");
};

const sanitizeRichHtmlFragment = (html: string): string => {
  if (!html.trim()) return "";
  if (typeof window === "undefined" || typeof window.DOMParser === "undefined") {
    return escapeHtml(html);
  }
  const parser = new window.DOMParser();
  const parsed = parser.parseFromString(`<body>${html}</body>`, "text/html");
  const body = parsed.body;
  body.querySelectorAll("script, style, iframe, object, embed").forEach((node) => node.remove());
  body.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) node.removeAttribute(attribute.name);
    });
    if (node instanceof HTMLAnchorElement) {
      const href = node.getAttribute("href") || "";
      if (!SAFE_PROTOCOL_RE.test(href)) node.removeAttribute("href");
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer nofollow");
    }
  });
  return body.innerHTML;
};

const plainFromLatex = (value: string): string =>
  stripMathDelimiters(value)
    .replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, "($1)/($2)")
    .replace(/\\sqrt\s*\{([^{}]+)\}/g, "sqrt($1)")
    .replace(/\\boxed\{([^}]+)\}/g, "$1")
    .replace(/\\text\{([^}]+)\}/g, "$1")
    .replace(/\\cdot/g, " * ")
    .replace(/\\times/g, " x ")
    .replace(/\\pm/g, " +/- ")
    .replace(/\\leq/g, " <= ")
    .replace(/\\geq/g, " >= ")
    .replace(/\\neq/g, " != ")
    .replace(/\\infty/g, " infinity ")
    .replace(/\\(sin|cos|tan|cot|sec|csc|log|ln|exp)\b/g, "$1")
    .replace(/\\([a-zA-Z]+)/g, "$1")
    .replace(/[{}]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const plainText = (value: string): string =>
  normalizeWhitespace(
    decodeHtmlEntities(value)
      .replace(MATH_DELIMITER_RE, (full) => plainFromLatex(full))
      .replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, "($1)/($2)")
      .replace(/\\sqrt\s*\{([^{}]+)\}/g, "sqrt($1)")
      .replace(/\\text\{([^}]+)\}/g, "$1")
      .replace(/\\neq/g, " != ")
      .replace(/\\leq/g, " <= ")
      .replace(/\\geq/g, " >= ")
      .replace(/[{}]/g, " ")
      .replace(/\\boxed\{([^}]+)\}/g, "$1")
      .replace(/\*\*/g, ""),
  );

const plainTextFromHtml = (value?: string): string => {
  if (!value) return "";
  if (typeof window === "undefined" || typeof window.DOMParser === "undefined") {
    return plainText(decodeHtmlEntities(value).replace(/<[^>]+>/g, " "));
  }
  const parser = new window.DOMParser();
  const parsed = parser.parseFromString(`<body>${decodeHtmlEntities(value)}</body>`, "text/html");
  return plainText(parsed.body.textContent || "");
};

const extractProblemText = (pages: CanvasPageData[]): string => {
  for (const page of pages) {
    for (const block of page.blocks || []) {
      if (block.type === "recognition" && block.latex.trim()) return block.latex;
    }
  }
  for (const page of pages) {
    for (const block of page.blocks || []) {
      if (block.type === "steps" && block.steps.length > 0) {
        const first = block.steps[0];
        const candidate = first.explanation || first.mathLatex || first.title;
        if (candidate) return candidate;
      }
    }
  }
  return "solution";
};

const slugify = (value: string): string => {
  const plain = plainText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return plain || "solution";
};

export const hasExportableSolution = (pages: CanvasPageData[]): boolean => {
  let hasProblem = false;
  let hasSteps = false;
  for (const page of pages) {
    for (const block of page.blocks || []) {
      if (block.type === "recognition" && block.latex.trim()) hasProblem = true;
      if (block.type === "steps" && block.steps.length > 0) hasSteps = true;
    }
  }
  return hasProblem && hasSteps;
};

export const suggestExportFileName = (
  payload: SolutionExportPayload,
  extension: "pdf" | "docx",
): string => {
  const slug = slugify(extractProblemText(payload.pages));
  const day = new Date(payload.generatedAt || Date.now()).toISOString().slice(0, 10);
  return `uask-solution-${slug}-${day}.${extension}`;
};

type PlotLike = {
  title?: string;
  xLabel?: string;
  yLabel?: string;
  points: { x: number; y: number }[];
};

const renderPlotSvg = (element: PlotLike): string => {
  if (element.points.length < 2) return "";
  const width = 520;
  const height = 240;
  const padding = 24;
  const xs = element.points.map((p) => p.x);
  const ys = element.points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(1e-9, maxX - minX);
  const spanY = Math.max(1e-9, maxY - minY);

  const path = element.points
    .map((p, idx) => {
      const px = padding + ((p.x - minX) / spanX) * (width - padding * 2);
      const py = height - padding - ((p.y - minY) / spanY) * (height - padding * 2);
      return `${idx === 0 ? "M" : "L"}${px.toFixed(2)} ${py.toFixed(2)}`;
    })
    .join(" ");

  return `
    <div class="plot-card">
      <div class="plot-title">${escapeHtml(element.title || "Graph")}</div>
      <svg viewBox="0 0 ${width} ${height}" class="plot-svg" role="img" aria-label="${escapeHtml(
    element.title || "Graph",
  )}">
        <rect x="0" y="0" width="${width}" height="${height}" fill="#fff" stroke="#d8dee9" />
        <path d="${path}" fill="none" stroke="#1f4f8a" stroke-width="2.2" />
      </svg>
      <div class="plot-axis-labels">
        <span>x: ${escapeHtml(element.xLabel || "x")}</span>
        <span>y: ${escapeHtml(element.yLabel || "y")}</span>
      </div>
    </div>
  `;
};

const renderStep = (step: StepRow, index: number): string => `
  <article class="step-card">
    <h4>Step ${step.k || index + 1}${step.title ? ` - ${escapeHtml(step.title)}` : ""}</h4>
    ${step.explanationRichHtml
    ? `<div class="step-prose rich-text">${sanitizeRichHtmlFragment(step.explanationRichHtml)}</div>`
    : (step.bodyMarkdown || step.explanation)
      ? `<div class="step-prose">${proseWithMathToHtml(step.bodyMarkdown || step.explanation || "")}</div>`
      : ""
  }
    ${step.mathLatex ? `<div class="step-math">${latexToHtml(step.mathLatex, true)}</div>` : ""}
  </article>
`;

const renderPage = (page: CanvasPageData, pageIndex: number): string => {
  const blocks = page.blocks || [];
  const blockHtml = blocks
    .map((block) => {
      if (block.type === "recognition") {
        return `
          <section class="section problem-section">
            <h3>Problem</h3>
            <div class="problem-content">${richMathToHtml(block.latex, true)}</div>
          </section>
        `;
      }
      if (block.type === "steps") {
        return `
          <section class="section steps-section">
            <div class="problem-statement-card">
               <div class="problem-statement-header">Problem Analysis</div>
               ${block.originalProblem ? `<div class="original-problem"><strong>Goal:</strong> ${proseWithMathToHtml(block.originalProblem)}</div>` : ""}
               ${block.assumptions && block.assumptions.length > 0 ? `
                 <div class="assumptions-box">
                   <div class="assumptions-title">Assumptions</div>
                   <ul class="assumptions-list">
                     ${block.assumptions.map(a => `<li>${proseWithMathToHtml(a)}</li>`).join("")}
                   </ul>
                 </div>
               ` : ""}
            </div>

            <h3>Step-by-step Solution</h3>
            ${block.domainConstraints && block.domainConstraints.length > 0
            ? `<div class="verification"><h4>Domain constraints</h4>${block.domainConstraints
              .map((item) => `<div class="verification-item">${proseWithMathToHtml(item)}</div>`)
              .join("")}</div>`
            : ""
          }
            ${block.steps.map((step, idx) => renderStep(step, idx)).join("")}
            
            ${block.commonMistakes && block.commonMistakes.length > 0 ? `
              <div class="mistakes-card">
                <div class="mistakes-header">Common Mistakes to Avoid</div>
                <ul class="mistakes-list">
                  ${block.commonMistakes.map(m => `<li>${proseWithMathToHtml(m)}</li>`).join("")}
                </ul>
              </div>
            ` : ""}

            ${block.verificationChecks && block.verificationChecks.length > 0
            ? `<div class="verification"><h4>Verification</h4>${block.verificationChecks
              .map(
                (check) =>
                  `<div class="verification-item"><strong>${escapeHtml(check.checkId)}:</strong> ${escapeHtml(
                    check.message,
                  )}${check.evidenceMath ? `<div class="verification-math">${latexToHtml(check.evidenceMath, false)}</div>` : ""
                  }</div>`,
              )
              .join("")}</div>`
            : ""
          }
            ${(block.result || (block.finalAnswer && (block.finalAnswer.answer_latex || block.finalAnswer.answer_text)))
            ? `
            <section class="section final-answer">
              <h3>Final Result</h3>
              <div class="final-answer-content">
                ${block.finalAnswer?.answer_latex
              ? latexToHtml(block.finalAnswer.answer_latex, true)
              : (block.result ? richMathToHtml(block.result, true) : "")}
              </div>
              ${(block.finalAnswer?.values?.length || block.finalAnswer?.units) ? `
                <div class="final-answer-details">
                  ${block.finalAnswer?.units ? `<div class="detail-item"><span class="detail-label">Units:</span> <span class="detail-value">${escapeHtml(block.finalAnswer.units)}</span></div>` : ""}
                  ${block.finalAnswer?.values?.map(v => `
                    <div class="detail-item">
                      <span class="detail-label">${escapeHtml(v.label)}:</span> 
                      <span class="detail-value">${latexToHtml(v.value_latex || v.value?.toString() || "", false)}</span>
                    </div>
                  `).join("")}
                </div>
              ` : ""}
            </section>`
            : ""
          }
            ${block.plots && block.plots.length > 0 ? `
              <div class="block-plots">
                ${block.plots.map(p => renderPlotSvg(p)).join("")}
              </div>
            ` : ""}
          </section>
        `;
      }
      return `
        <section class="section notes-section">
          <h3>Notes</h3>
          <div>${proseWithMathToHtml(block.text)}</div>
        </section>
      `;
    })
    .join("");

  const elementHtml = page.elements
    .map((element) => {
      if (element.type === "math") {
        return `<section class="section"><h3>Math Block</h3><div class="step-math">${latexToHtml(
          element.latexRaw,
          true,
        )}</div></section>`;
      }
      if (element.type === "text") {
        const richHtml = sanitizeRichHtmlFragment(element.richTextHtml || "");
        return `<section class="section"><h3>Text Block</h3><div class="rich-text-export">${richHtml || proseWithMathToHtml(element.text)
          }</div></section>`;
      }
      if (element.type === "plot") {
        return `<section class="section"><h3>Graph</h3>${renderPlotSvg(element)}</section>`;
      }
      return "";
    })
    .join("");

  return `
    <section class="paper-page ${pageIndex > 0 ? "paper-page-break" : ""}">
      <div class="page-title">Canvas Page ${pageIndex + 1}${page.title ? ` - ${escapeHtml(page.title)}` : ""}</div>
      ${blockHtml}
      ${elementHtml}
    </section>
  `;
};

export const buildExportHtml = (payload: SolutionExportPayload): string => {
  const generatedAt = new Date(payload.generatedAt || Date.now());
  const generatedLabel = generatedAt.toLocaleString();
  const fileTitle = suggestExportFileName(payload, "pdf");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(fileTitle)}</title>
  <style>
    :root { color-scheme: light; }
    body { margin: 0; background: #f4f6f8; font-family: "Segoe UI", Arial, sans-serif; color: #101828; }
    .doc-root { max-width: 980px; margin: 0 auto; padding: 24px; }
    .sheet {
      background: #fff; border: 1px solid #d9dde5; border-radius: 12px;
      padding: 28px 34px; margin-bottom: 24px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    }
    .brand { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #48617f; }
    .title { margin: 8px 0 6px; font-size: 30px; font-weight: 700; }
    .meta { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: #55657f; border-bottom: 1px solid #e4e7ed; padding-bottom: 10px; margin-bottom: 14px; }
    .page-title { font-size: 14px; font-weight: 700; margin: 4px 0 12px; color: #1f3f63; }
    .section { border: 1px solid #e5e8ee; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; break-inside: avoid; page-break-inside: avoid; }
    .section h3 { margin: 0 0 10px; font-size: 16px; color: #1f3550; }
    .step-card { border: 1px solid #ecf0f5; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; break-inside: avoid; page-break-inside: avoid; }
    .step-card h4 { margin: 0 0 8px; font-size: 14px; color: #17406f; }
    .step-prose { font-size: 14px; line-height: 1.6; }
    .step-math { margin-top: 8px; text-align: center; }
    .final-answer-content { font-size: 16px; font-weight: 700; text-align: center; }
    .verification-item { margin-bottom: 8px; font-size: 13px; line-height: 1.5; }
    .verification-math { margin-top: 5px; }
    .rich-text-export p { margin: 0 0 8px; }
    .rich-text-export ul, .rich-text-export ol { margin: 0 0 8px 20px; }
    .rich-text-export table { border-collapse: collapse; width: 100%; table-layout: fixed; }
    .rich-text-export td, .rich-text-export th { border: 1px solid #d7deea; padding: 6px 8px; }
    .rich-text-export a { color: #1b5ca1; text-decoration: underline; }
    .plot-card { border: 1px solid #e1e6ee; border-radius: 10px; padding: 10px; break-inside: avoid; }
    .plot-title { font-size: 13px; font-weight: 700; margin-bottom: 6px; }
    .plot-svg { width: 100%; height: auto; max-height: 260px; background: #fff; }
    .plot-axis-labels { display: flex; justify-content: space-between; font-size: 12px; color: #42526a; margin-top: 6px; }
    .problem-statement-card { background: #f0fdf4; border-left: 4px solid #16a34a; padding: 16px; margin-bottom: 20px; border-radius: 4px; }
    .problem-statement-header { font-size: 11px; font-weight: 900; color: #166534; text-transform: uppercase; margin-bottom: 8px; }
    .assumptions-box { margin-top: 12px; }
    .assumptions-title { font-size: 10px; font-weight: 800; color: #166534; text-transform: uppercase; margin-bottom: 4px; }
    .assumptions-list { margin: 0; padding-left: 18px; font-size: 12px; color: #374151; }
    .mistakes-card { background: #fffbeb; border: 1px solid #fde68a; padding: 16px; margin: 20px 0; border-radius: 8px; }
    .mistakes-header { color: #92400e; font-weight: 700; font-size: 14px; margin-bottom: 8px; }
    .mistakes-list { margin: 0; padding-left: 20px; font-size: 13px; color: #78350f; }
    .final-answer-details { display: flex; flex-wrap: wrap; justify-content: center; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
    .detail-item { font-size: 14px; }
    .detail-label { font-weight: 700; color: #6b7280; text-transform: uppercase; font-size: 10px; margin-right: 4px; }
    .detail-value { font-weight: 600; color: #111827; }
    .paper-page-break { page-break-before: always; }
    math { font-size: 1.05em; color: #101828; }
    .step-math math, .verification-math math { display: inline-block; }
    @media print {
      body { margin: 0; background: #fff; }
      .doc-root { max-width: none; margin: 0; padding: 0; }
      .sheet { border: 0; border-radius: 0; box-shadow: none; margin: 0; padding: 0.6in; }
      [data-no-export="true"] { display: none !important; }
      .paper-page-break { break-before: page; page-break-before: always; }
      .section, .step-card, .plot-card { break-inside: avoid; page-break-inside: avoid; }
      @page { size: Letter portrait; margin: 0.6in; }
    }
  </style>
</head>
<body>
  <main class="doc-root">
    <article class="sheet">
      <div class="brand">uask.ai</div>
      <h1 class="title">${escapeHtml(payload.title || "Solution")}</h1>
      <div class="meta">
        <span><strong>Date:</strong> ${escapeHtml(generatedLabel)}</span>
        ${payload.solveId ? `<span><strong>Solve ID:</strong> ${escapeHtml(payload.solveId)}</span>` : ""}
        ${payload.tier ? `<span><strong>Tier:</strong> ${escapeHtml(payload.tier)}</span>` : ""}
      </div>
      ${payload.pages.map((page, index) => renderPage(page, index)).join("")}
    </article>
  </main>
  <script>
    window.addEventListener("load", () => { setTimeout(() => window.print(), 220); });
    window.addEventListener("afterprint", () => { window.close(); });
  </script>
</body>
</html>`;
};

const notifyExportError = (message: string) => {
  if (typeof window !== "undefined" && typeof window.alert === "function") {
    window.alert(message);
  }
};

const openPdfInPopupOrIframe = (payload: SolutionExportPayload) => {
  const html = buildExportHtml(payload);
  const popup = typeof window !== "undefined" ? window.open("", "_blank", "noopener,noreferrer") : null;
  if (popup && popup.document) {
    popup.document.open();
    popup.document.write(html);
    popup.document.close();
    return;
  }
  if (typeof document !== "undefined") {
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.style.position = "fixed";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    frame.srcdoc = html;
    document.body.appendChild(frame);
  }
};

export const exportCanvasToPdf = async (payload: SolutionExportPayload): Promise<void> => {
  if (typeof fetch !== "function") {
    openPdfInPopupOrIframe(payload);
    return;
  }
  try {
    const exportPayload = mapToExportPayload(payload);
    const res = await fetch("/api/export/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(exportPayload),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Export failed: ${errText}`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestExportFileName(payload, "pdf");
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  } catch (error) {
    console.error("PDF Export Error:", error);
    openPdfInPopupOrIframe(payload);
    notifyExportError("PDF export failed. Opened browser print fallback.");
  }
};

const mapToExportPayload = (payload: SolutionExportPayload): ExportSolutionPayload => {
  return {
    docTitle: payload.title || "Solution",
    subtitle: payload.solveId ? `ID: ${payload.solveId}${payload.tier ? ` | ${payload.tier}` : ""}` : undefined,
    createdAtISO: payload.generatedAt || new Date().toISOString(),
    pages: payload.pages.map((page, idx) => ({
      pageTitle: page.title || `Page ${idx + 1}`,
      blocks: (page.blocks || []).flatMap((block) => {
        if (block.type === "recognition") {
          const normalizedProblemLatex = decodeHtmlEntities(block.latex || "");
          return [{
            type: "problem",
            title: "Problem",
            body: plainText(normalizedProblemLatex),
            math: [normalizedProblemLatex],
          }];
        }
        if (block.type === "steps") {
          type ExportBlock = ExportSolutionPayload["pages"][number]["blocks"][number];
          const out: ExportBlock[] = [];

          out.push({
            type: "problem",
            title: "Problem Analysis",
            body: block.originalProblem ? `Goal: ${plainText(block.originalProblem)}` : "",
            assumptions: (block.assumptions || []).map((item) => plainText(item)),
            originalText: block.originalProblem ? plainText(block.originalProblem) : undefined
          });

          if (block.domainConstraints?.length) {
            out.push({
              type: "note",
              title: "Domain Constraints",
              body: block.domainConstraints.map(c => plainText(c)).join("\n")
            });
          }

          block.steps.forEach((step, stepIdx) => {
            const body = plainTextFromHtml(step.explanationRichHtml) || plainText(step.bodyMarkdown || step.explanation || "");
            const normalizedStepMath = step.mathLatex ? decodeHtmlEntities(step.mathLatex) : undefined;
            out.push({
              type: "step",
              k: step.k || stepIdx + 1,
              title: plainText(step.title || ""),
              body: body,
              math: normalizedStepMath ? [normalizedStepMath] : undefined
            });
          });

          if (block.commonMistakes?.length) {
            out.push({
              type: "mistakes",
              title: "Common Mistakes to Avoid",
              list: block.commonMistakes
            });
          }

          if (block.verificationChecks?.length) {
            const body = block.verificationChecks.map(c => `${c.checkId}: ${plainText(c.message)}`).join("\n");
            out.push({ type: "note", title: "Verification", body });
          }

          const resMath = block.finalAnswer?.answer_latex || block.result;
          const finalText = plainText(block.finalAnswer?.answer_text || "");
          const normalizedFinalMath = resMath ? decodeHtmlEntities(resMath) : undefined;
          if (resMath || block.finalAnswer?.answer_text) {
            out.push({
              type: "final",
              label: "Final Result",
              body: block.autocorrectApplied
                ? `${finalText ? `${finalText} ` : ""}(Verified)`.trim()
                : finalText,
              math: normalizedFinalMath ? [normalizedFinalMath] : undefined,
              units: block.finalAnswer?.units ? plainText(block.finalAnswer.units) : undefined,
              values: block.finalAnswer?.values?.map(v => ({
                label: plainText(v.label),
                value: plainText(v.value_latex || v.value?.toString() || "")
              }))
            });
          }

          if (block.plots?.length) {
            block.plots.forEach(p => {
              out.push({
                type: "plot",
                title: p.title || "Graph",
                xLabel: p.xLabel || "x",
                yLabel: p.yLabel || "y",
                points: p.points
              });
            });
          }
          return out;
        }
        if (block.type === "text") {
          return [{ type: "note", title: "Notes", body: plainText(block.text) }];
        }
        return [];
      })
    }))
  };
};

export const exportCanvasToDocx = async (payload: SolutionExportPayload): Promise<void> => {
  if (typeof fetch !== "function") {
    const err = new Error("DOCX export is unavailable in this environment (fetch missing).");
    console.error("DOCX Export Error:", err);
    notifyExportError("DOCX export unavailable in this environment.");
    throw err;
  }
  try {
    const exportPayload = mapToExportPayload(payload);
    const res = await fetch("/api/export/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(exportPayload),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Export failed: ${errText}`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestExportFileName(payload, "docx");
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  } catch (error) {
    console.error("DOCX Export Error:", error);
    notifyExportError("DOCX export failed. Check console for details.");
    throw error;
  }
};
