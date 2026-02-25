import { NextResponse } from "next/server";
import { BACKEND_URL, FALLBACK_BACKEND_URL, requireAdminAuth } from "../../_proxy";

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const limit = searchParams.get("limit") || "200";
    const phone = searchParams.get("phone") || "";
    const direction = searchParams.get("direction") || "";
    const qs = new URLSearchParams({ limit });
    if (phone) qs.set("phone", phone);
    if (direction) qs.set("direction", direction);
    const auth = requireAdminAuth(request);
    if (auth instanceof NextResponse) return auth;
    const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);

    let lastError: unknown = null;
    for (const baseUrl of urls) {
        try {
            const response = await fetch(`${baseUrl}/api/admin/whatsapp/monitor/export?${qs.toString()}`, {
                method: "GET",
                headers: {
                    Authorization: auth,
                },
            });
            const blob = await response.blob();
            return new NextResponse(blob, {
                headers: {
                    "Content-Type": "text/csv",
                    "Content-Disposition": "attachment; filename=whatsapp_monitor.csv",
                },
            });
        } catch (err) {
            lastError = err;
        }
    }

    console.error("Error exporting WhatsApp monitor:", lastError);
    return NextResponse.json(
        { error: "Failed to export WhatsApp monitor" },
        { status: 500 }
    );
}
