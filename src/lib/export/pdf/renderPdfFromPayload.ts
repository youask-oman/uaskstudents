import type { ExportSolutionPayload } from "@/lib/export/docx/validate";
import { renderHtmlFromPayload } from "@/lib/export/pdf/renderHtmlFromPayload";
import { renderPdf } from "@/lib/export/pdf/renderPdf";

export async function renderPdfFromPayload(payload: ExportSolutionPayload): Promise<Buffer> {
    const html = renderHtmlFromPayload(payload);
    return renderPdf({
        html,
        docTitle: payload.docTitle,
        footerText: `Uask AI - ${payload.docTitle}`,
    });
}
