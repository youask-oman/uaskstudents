import { NextRequest, NextResponse } from "next/server";
import { sanitizePayloadOrThrow } from "@/lib/export/docx/validate";
import { renderHtmlFromPayload } from "@/lib/export/pdf/renderHtmlFromPayload";
import { renderPdf } from "@/lib/export/pdf/renderPdf";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
    const startTime = Date.now();
    try {
        const body = await req.json();

        // 1. Validate payload
        const payload = sanitizePayloadOrThrow(body);

        // 2. Generate HTML
        const html = renderHtmlFromPayload(payload);

        // 3. Render PDF using Playwright
        const pdfBuffer = await renderPdf({
            html,
            docTitle: payload.docTitle,
            footerText: `Uask AI - ${payload.docTitle}`
        });

        const duration = Date.now() - startTime;
        const pageCount = payload.pages.length;
        const totalBlocks = payload.pages.reduce((acc, p) => acc + p.blocks.length, 0);
        const mathBlocks = payload.pages.reduce((acc, p) =>
            acc + p.blocks.reduce((bacc, b) => bacc + (("math" in b && b.math?.length) ? b.math.length : 0), 0), 0
        );

        console.log(`[PDF Export] Success. Time: ${duration}ms, Pages: ${pageCount}, Blocks: ${totalBlocks}, Math: ${mathBlocks}`);

        // 4. Return PDF
        return new NextResponse(new Uint8Array(pdfBuffer), {
            status: 200,
            headers: {
                "Content-Type": "application/pdf",
                "Content-Disposition": `attachment; filename="${encodeURIComponent(payload.docTitle)}.pdf"`,
                "X-Export-Time": duration.toString(),
            },
        });

    } catch (err: unknown) {
        console.error("[PDF Export] Error:", err);

        if (err && typeof err === "object" && "name" in err && (err as { name?: string }).name === "ZodError") {
            return NextResponse.json({
                error: "Invalid payload",
                details: (err as { errors?: unknown }).errors
            }, { status: 400 });
        }

        return NextResponse.json({
            error: "Failed to generate PDF",
            message: err instanceof Error ? err.message : String(err)
        }, { status: 500 });
    }
}
