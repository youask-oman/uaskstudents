// lib/export/pdf/renderPdfFromPayload.ts
import type { ExportSolutionPayload } from "@/lib/export/docx/validate";
import { chromium } from "playwright";
import { renderHtmlFromPayload } from "./renderHtmlFromPayload";

export async function renderPdfFromPayload(payload: ExportSolutionPayload): Promise<Buffer> {
    const html = renderHtmlFromPayload(payload);

    const browser = await chromium.launch();
    try {
        const page = await browser.newPage({ deviceScaleFactor: 2 });
        await page.setContent(html, { waitUntil: "networkidle" });

        const header = `
      <div style="font-size:9px; width:100%; padding:0 16mm; color:#64748b;">
        <span>${escapeHtml(payload.docTitle)}</span>
      </div>
    `;

        const footer = `
      <div style="font-size:9px; width:100%; padding:0 16mm; color:#64748b; display:flex; justify-content:space-between;">
        <span>${escapeHtml(new Date(payload.createdAtISO).toLocaleString())}</span>
        <span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span>
      </div>
    `;

        const pdf = await page.pdf({
            format: "A4",
            printBackground: true,
            displayHeaderFooter: true,
            headerTemplate: header,
            footerTemplate: footer,
            margin: { top: "22mm", bottom: "18mm", left: "16mm", right: "16mm" },
        });

        return Buffer.from(pdf);
    } finally {
        await browser.close();
    }
}

function escapeHtml(s: string) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
