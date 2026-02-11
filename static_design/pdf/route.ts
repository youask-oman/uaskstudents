// app/api/export/pdf/route.ts
import { NextResponse } from "next/server";
import { sanitizePayloadOrThrow } from "@/lib/export/docx/validate"; // reuse
import { renderPdfFromPayload } from "@/lib/export/pdf/renderPdfFromPayload";

export const runtime = "nodejs";

export async function POST(req: Request) {
    try {
        const payload = sanitizePayloadOrThrow(await req.json());
        const pdf = await renderPdfFromPayload(payload);

        const fileName = `${payload.docTitle}`.replace(/[^\w\d-_ ]+/g, "").slice(0, 80) || "export";
        return new NextResponse(new Uint8Array(pdf), {
            status: 200,
            headers: {
                "Content-Type": "application/pdf",
                "Content-Disposition": `attachment; filename="${fileName}.pdf"`,
            },
        });
    } catch (e: unknown) {
        const message = e instanceof Error ? e.message : String(e);
        console.error("[PDF_EXPORT_FAIL]", e);
        return NextResponse.json(
            { ok: false, error: "PDF export failed", detail: message },
            { status: 500 }
        );
    }
}
