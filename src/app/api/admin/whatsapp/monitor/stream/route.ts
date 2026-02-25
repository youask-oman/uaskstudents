import { NextResponse } from "next/server";
import { BACKEND_URL, FALLBACK_BACKEND_URL, requireAdminAuth } from "../../_proxy";

export async function GET(request: Request) {
    const auth = requireAdminAuth(request);
    if (auth instanceof NextResponse) return auth;
    const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
    let lastError: unknown = null;

    for (const baseUrl of urls) {
        try {
            const response = await fetch(`${baseUrl}/api/admin/whatsapp/monitor/stream`, {
                method: "GET",
                headers: {
                    Authorization: auth,
                },
            });

            if (!response.body) {
                throw new Error("No stream body");
            }

            return new NextResponse(response.body, {
                headers: {
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            });
        } catch (err) {
            lastError = err;
        }
    }

    console.error("Error streaming WhatsApp monitor:", lastError);
    return NextResponse.json(
        { error: "Failed to stream WhatsApp monitor" },
        { status: 500 }
    );
}
