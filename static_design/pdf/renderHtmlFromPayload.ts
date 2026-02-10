// lib/export/pdf/renderHtmlFromPayload.ts
import type { ExportSolutionPayload } from "@/lib/export/docx/validate";

export function renderHtmlFromPayload(payload: ExportSolutionPayload) {
    const safe = (s: string) =>
        s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    const blocksHtml = payload.pages
        .map((page, idx) => {
            const pageBreak = idx === 0 ? "" : `<div class="page-break"></div>`;
            return `
        ${pageBreak}
        <section class="page">
          <h2 class="page-title">${safe(page.pageTitle)}</h2>
          ${page.blocks.map((b) => renderBlock(b)).join("")}
        </section>
      `;
        })
        .join("");

    function renderMath(math?: string[]) {
        if (!math?.length) return "";
        return math
            .map((latex) => `<div class="math-block" data-latex="${encodeURIComponent(latex)}"></div>`)
            .join("");
    }

    type Block = ExportSolutionPayload["pages"][number]["blocks"][number];
    function renderBlock(b: Block) {
        if (b.type === "problem") {
            return `
        <div class="card card-problem">
          <div class="card-title">${safe(b.title)}</div>
          <div class="card-body">${safe(b.body)}</div>
          ${renderMath(b.math)}
        </div>
      `;
        }
        if (b.type === "step") {
            return `
        <div class="card card-step avoid-break">
          <div class="step-head">
            <div class="step-badge">STEP ${b.k}</div>
            <div class="step-title">${safe(b.title)}</div>
          </div>
          <div class="card-body">${safe(b.body)}</div>
          ${renderMath(b.math)}
        </div>
      `;
        }
        if (b.type === "final") {
            return `
        <div class="card card-final avoid-break">
          <div class="final-label">${safe(b.label || "Final Answer")}</div>
          <div class="final-body">${safe(b.body)}</div>
          ${renderMath(b.math)}
        </div>
      `;
        }
        if (b.type === "note") {
            return `
        <div class="card card-note">
          ${b.title ? `<div class="card-title">${safe(b.title)}</div>` : ""}
          <div class="card-body">${safe(b.body)}</div>
        </div>
      `;
        }
        return "";
    }

    return `
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">
  <style>
    @page { size: A4; margin: 18mm 16mm; }
    body { font-family: Inter, Arial, sans-serif; color: #0f172a; }
    .doc-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
    .doc-meta { font-size: 11px; color: #475569; margin: 0 0 14px; }

    .page-title { font-size: 14px; font-weight: 800; margin: 16px 0 10px; color: #334155; }

    .card {
      border: 1px solid #e5e8ee;
      border-radius: 12px;
      padding: 14px 14px;
      margin: 10px 0;
      background: #fff;
    }
    .card-problem { background: #f7faff; }
    .card-note { background: #fbfbfc; }
    .card-final { background: #1fa971; color: #fff; }
    .card-title { font-weight: 800; margin-bottom: 6px; }
    .card-body { font-size: 12px; line-height: 1.45; white-space: pre-wrap; }

    .step-head { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
    .step-badge {
      background: #eaf2ff;
      color: #1e3a8a;
      font-weight: 800;
      font-size: 11px;
      padding: 6px 10px;
      border-radius: 999px;
      display: inline-block;
    }
    .step-title { font-weight: 800; font-size: 12px; color: #0f172a; }

    .final-label { font-weight: 900; font-size: 12px; }
    .final-body { font-weight: 900; font-size: 12px; margin-top: 6px; white-space: pre-wrap; }

    .math-block { margin-top: 10px; text-align: center; }
    .katex { font-size: 1.05em; } /* tune for premium look */

    .page-break { page-break-before: always; }
    .avoid-break { break-inside: avoid; page-break-inside: avoid; }
  </style>
</head>
<body>
  <div class="doc-title">${safe(payload.docTitle)}</div>
  <div class="doc-meta">Exported: ${safe(new Date(payload.createdAtISO).toLocaleString())}</div>

  ${blocksHtml}

  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"></script>
  <script>
    const blocks = Array.from(document.querySelectorAll(".math-block"));
    for (const el of blocks) {
      const latex = decodeURIComponent(el.getAttribute("data-latex") || "");
      try {
        katex.render(latex, el, { throwOnError: false, displayMode: true });
      } catch (e) {
        el.textContent = latex;
      }
    }
  </script>
</body>
</html>
`;
}
