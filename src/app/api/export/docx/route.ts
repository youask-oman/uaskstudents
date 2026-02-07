// app/api/export/docx/route.ts
import { NextResponse } from "next/server";
import { buildDocxFromPayload } from "@/lib/export/docx/buildDocxFromPayload";
import { sanitizePayloadOrThrow } from "@/lib/export/docx/validate";
import { docxToBuffer } from "@/lib/export/docx/docxToBuffer";

export const runtime = "nodejs"; // needed for playwright/docx

export async function POST(req: Request) {
    try {
        const payload = await req.json();
        const safe = sanitizePayloadOrThrow(payload);

        const doc = await buildDocxFromPayload(safe);
        const buf = await docxToBuffer(doc);

        const fileName = `${safe.docTitle}`.replace(/[^\w\d-_ ]+/g, "").slice(0, 80) || "export";
        return new NextResponse(buf as any, {
            status: 200,
            headers: {
                "Content-Type":
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "Content-Disposition": `attachment; filename="${fileName}.docx"`,
            },
        });
    } catch (e: any) {
        console.error("[DOCX_EXPORT_FAIL]", e);
        return NextResponse.json(
            { ok: false, error: "DOCX export failed", detail: String(e?.message || e) },
            { status: 500 }
        );
    }
}
