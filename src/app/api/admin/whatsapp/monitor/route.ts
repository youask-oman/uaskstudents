import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || process.env.API_BACKEND_BASE_URL || `http://orchestrator:${process.env.API_BACKEND_PORT || "9000"}`;
const INTERNAL_KEY = process.env.WHATSAPP_INTERNAL_KEY || "";

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const limit = searchParams.get("limit") || "50";
    const phone = searchParams.get("phone") || "";
    const direction = searchParams.get("direction") || "";
    const qs = new URLSearchParams({ limit });
    if (phone) qs.set("phone", phone);
    if (direction) qs.set("direction", direction);
    const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);

    let lastError: unknown = null;
    for (const baseUrl of urls) {
        try {
            const response = await fetch(`${baseUrl}/api/v1/admin/whatsapp/monitor?${qs.toString()}`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    ...(INTERNAL_KEY ? { "X-UASK-INTERNAL-KEY": INTERNAL_KEY } : {}),
                },
            });
            const data = await response.json();
            return NextResponse.json(data);
        } catch (err) {
            lastError = err;
        }
    }

    console.error("Error fetching WhatsApp monitor:", lastError);
    return NextResponse.json(
        { error: "Failed to fetch WhatsApp monitor" },
        { status: 500 }
    );
}
