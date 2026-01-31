import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || "http://orchestrator:8000";
const INTERNAL_KEY = process.env.WHATSAPP_INTERNAL_KEY || "";

export async function GET() {
    const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
    let lastError: unknown = null;

    for (const baseUrl of urls) {
        try {
            const response = await fetch(`${baseUrl}/api/v1/admin/whatsapp/monitor/stream`, {
                method: "GET",
                headers: {
                    ...(INTERNAL_KEY ? { "X-UASK-INTERNAL-KEY": INTERNAL_KEY } : {}),
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
